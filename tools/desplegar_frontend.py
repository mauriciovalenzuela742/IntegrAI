#!/usr/bin/env python3
"""Despliega el frontend React (frontend/) en la web de IntegrAI (CloudFront).

    python tools/desplegar_frontend.py configurar   # una vez: bucket S3 privado + OAC + función SPA + comportamientos
    python tools/desplegar_frontend.py subir        # cada versión: build → S3 → invalidación
    python tools/desplegar_frontend.py revertir     # la raíz vuelve al dashboard Streamlit (:80)

Resultado en la distribución (se ubica por el comentario "IntegrAI", igual que tools/cloudfront_aws.py):
    /              → frontend React (S3 privado vía OAC; SPA: rutas sin extensión → /index.html)
    /streamlit*    → dashboard Streamlit en la EC2 (:80, con --server.baseUrlPath=streamlit)
    /api/*         → API de lectura (:8000): datos vivos para el dashboard
    /procesar*, /clasificar, /health → API (:8000), sin cambios

Se publican SOLO index.html, assets/, los 6 CSV sintéticos y recomendaciones.json.
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import time
from pathlib import Path

import boto3

RAIZ = Path(__file__).resolve().parent.parent
REGION = os.getenv("AWS_REGION", "us-east-1")
COMMENT = os.getenv("INTEGRA_CF_COMMENT", "IntegrAI")
CSV_USADOS = ["ruta_niveles.csv", "jardines.csv", "ninos.csv", "observaciones.csv",
              "manifestaciones.csv", "observacion_manifestaciones.csv", "recomendaciones.json"]
FUNCION_SPA = "integrai-spa-rewrite"
ORIGEN_S3 = "frontend-s3"
OAC = "integrai-frontend-oac"
CACHE_OPTIMIZADO = "658327ea-f89d-4fab-a63d-7e88639e58f6"   # Managed-CachingOptimized
CACHE_DESACTIVADO = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"  # Managed-CachingDisabled
TODO_VIEWER = "216adef6-5c7f-47e4-b989-5492eafa07d3"        # Managed-AllViewer

s = boto3.Session(region_name=REGION)
cf, s3 = s.client("cloudfront"), s.client("s3")
CUENTA = s.client("sts").get_caller_identity()["Account"]
BUCKET = os.getenv("INTEGRA_FRONTEND_BUCKET", f"integrai-frontend-{CUENTA}")

# Reescritura SPA. Si se agrega Basic auth (tools/cloudfront_aws.py auth-basica), ambas lógicas deben
# ir en UNA función: CloudFront admite una sola función viewer-request por comportamiento.
CODIGO_SPA = """function handler(event) {
  var r = event.request;
  if (r.uri.indexOf('.') === -1) { r.uri = '/index.html'; }
  return r;
}
"""


def _distribucion() -> dict:
    for d in cf.list_distributions().get("DistributionList", {}).get("Items", []):
        if COMMENT in d.get("Comment", ""):
            return d
    sys.exit("no se encontró la distribución de IntegrAI")


def _bucket() -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
        print("bucket existe:", BUCKET)
    except s3.exceptions.ClientError:
        s3.create_bucket(Bucket=BUCKET)
        print("bucket creado:", BUCKET)
    s3.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=BUCKET, ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    s3.put_bucket_ownership_controls(Bucket=BUCKET, OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]})
    s3.put_bucket_tagging(Bucket=BUCKET, Tagging={"TagSet": [{"Key": "proyecto", "Value": "integra-e1"}]})


def _oac() -> str:
    for o in cf.list_origin_access_controls().get("OriginAccessControlList", {}).get("Items", []):
        if o["Name"] == OAC:
            return o["Id"]
    return cf.create_origin_access_control(OriginAccessControlConfig={
        "Name": OAC, "Description": "IntegrAI frontend (S3 privado)", "SigningProtocol": "sigv4",
        "SigningBehavior": "always", "OriginAccessControlOriginType": "s3"})["OriginAccessControl"]["Id"]


def _funcion_spa() -> str:
    cfg = {"Comment": "IntegrAI: SPA rewrite (rutas sin extensión -> /index.html)", "Runtime": "cloudfront-js-2.0"}
    try:
        etag = cf.describe_function(Name=FUNCION_SPA, Stage="DEVELOPMENT")["ETag"]
        etag = cf.update_function(Name=FUNCION_SPA, IfMatch=etag, FunctionConfig=cfg, FunctionCode=CODIGO_SPA.encode())["ETag"]
    except cf.exceptions.NoSuchFunctionExists:
        etag = cf.create_function(Name=FUNCION_SPA, FunctionConfig=cfg, FunctionCode=CODIGO_SPA.encode())["ETag"]
    return cf.publish_function(Name=FUNCION_SPA, IfMatch=etag)["FunctionSummary"]["FunctionMetadata"]["FunctionARN"]


def configurar() -> None:
    _bucket()
    oac, fn = _oac(), _funcion_spa()
    d = _distribucion()
    r = cf.get_distribution_config(Id=d["Id"]); cfg, etag = r["DistributionConfig"], r["ETag"]
    # origen S3 privado
    origenes = [o for o in cfg["Origins"]["Items"] if o["Id"] != ORIGEN_S3]
    origenes.append({"Id": ORIGEN_S3, "DomainName": f"{BUCKET}.s3.{REGION}.amazonaws.com", "OriginPath": "",
                     "CustomHeaders": {"Quantity": 0}, "S3OriginConfig": {"OriginAccessIdentity": ""},
                     "OriginAccessControlId": oac, "ConnectionAttempts": 3, "ConnectionTimeout": 10})
    cfg["Origins"] = {"Quantity": len(origenes), "Items": origenes}
    # el origen del dashboard (puerto 80), para /streamlit*
    dash = next(o["Id"] for o in origenes if o.get("CustomOriginConfig", {}).get("HTTPPort") == 80)
    viejo = cfg["DefaultCacheBehavior"]
    nuevo = dict(viejo)
    nuevo.update({"TargetOriginId": ORIGEN_S3, "CachePolicyId": CACHE_OPTIMIZADO, "Compress": True,
                  "FunctionAssociations": {"Quantity": 1, "Items": [{"EventType": "viewer-request", "FunctionARN": fn}]}})
    nuevo.pop("OriginRequestPolicyId", None)
    nuevo["AllowedMethods"] = {"Quantity": 2, "Items": ["GET", "HEAD"], "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}}
    cfg["DefaultCacheBehavior"] = nuevo
    # Streamlit pasa a /streamlit* (mismo comportamiento que tenía la raíz: sin caché, todo el viewer)
    otros = [b for b in cfg.get("CacheBehaviors", {}).get("Items", []) if b["PathPattern"] != "/streamlit*"]
    st = {k: v for k, v in viejo.items() if k not in ("FunctionAssociations",)}
    st.update({"PathPattern": "/streamlit*", "TargetOriginId": dash, "CachePolicyId": CACHE_DESACTIVADO,
               "OriginRequestPolicyId": TODO_VIEWER, "FunctionAssociations": {"Quantity": 0}})
    st["AllowedMethods"] = {"Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                            "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}}
    otros.append(st)
    # API de lectura del dashboard (/api/*) -> mismo origen que la API (:8000)
    api = next(o["Id"] for o in origenes if o.get("CustomOriginConfig", {}).get("HTTPPort") == 8000)
    api_b = {k: v for k, v in viejo.items() if k not in ("FunctionAssociations",)}
    api_b.update({"PathPattern": "/api/*", "TargetOriginId": api, "CachePolicyId": CACHE_DESACTIVADO,
                  "OriginRequestPolicyId": TODO_VIEWER, "FunctionAssociations": {"Quantity": 0}})
    api_b["AllowedMethods"] = {"Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                               "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}}
    otros = [b for b in otros if b["PathPattern"] != "/api/*"] + [api_b]
    cfg["CacheBehaviors"] = {"Quantity": len(otros), "Items": otros}
    cfg["DefaultRootObject"] = "index.html"
    cf.update_distribution(Id=d["Id"], IfMatch=etag, DistributionConfig=cfg)
    # solo esta distribución puede leer el bucket
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{
        "Sid": "SoloCloudFrontIntegrAI", "Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"},
        "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{BUCKET}/*",
        "Condition": {"StringEquals": {"AWS:SourceArn": f"arn:aws:cloudfront::{CUENTA}:distribution/{d['Id']}"}}}]}))
    print("configurado: / -> frontend (S3), /streamlit* -> dashboard, API sin cambios")


def subir(build: bool = True) -> None:
    fe = RAIZ / "frontend"
    if build:
        # vite.config.ts usa base '/IntegrAI/' para GitHub Pages (PR #22); en CloudFront la app vive en la raíz.
        # VITE_API_BASE="" -> el dashboard lee datos VIVOS vía /api/* (mismo origen; ver el behavior /api/* abajo).
        env = {**os.environ, "VITE_API_BASE": os.getenv("VITE_API_BASE", ""),
               "VITE_REVISION": os.getenv("VITE_REVISION", "api")}  # la profesora usa el backend real
        subprocess.run("npm ci --no-audit --no-fund && npm run build -- --base=/", cwd=fe, shell=True, check=True, env=env)
    dist = fe / "dist"
    archivos = [dist / "index.html"] + sorted((dist / "assets").rglob("*")) + [dist / c for c in CSV_USADOS]
    for f in archivos:
        if not f.is_file():
            continue
        clave = f.relative_to(dist).as_posix()
        tipo = "text/csv; charset=utf-8" if f.suffix == ".csv" else (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        cache = ("no-cache" if f.name == "index.html" else
                 "public, max-age=31536000, immutable" if clave.startswith("assets/") else "public, max-age=300")
        s3.upload_file(str(f), BUCKET, clave, ExtraArgs={"ContentType": tipo, "CacheControl": cache})
    print(f"subidos {len(archivos)} archivos a s3://{BUCKET}")
    d = _distribucion()
    cf.create_invalidation(DistributionId=d["Id"], InvalidationBatch={
        "Paths": {"Quantity": 1, "Items": ["/index.html"]}, "CallerReference": str(time.time())})
    print("invalidación de /index.html creada")


def revertir() -> None:
    d = _distribucion()
    r = cf.get_distribution_config(Id=d["Id"]); cfg = r["DistributionConfig"]
    st = next(b for b in cfg["CacheBehaviors"]["Items"] if b["PathPattern"] == "/streamlit*")
    raiz = {k: v for k, v in st.items() if k != "PathPattern"}
    cfg["DefaultCacheBehavior"] = raiz
    cfg["CacheBehaviors"]["Items"] = [b for b in cfg["CacheBehaviors"]["Items"] if b["PathPattern"] != "/streamlit*"]
    cfg["CacheBehaviors"]["Quantity"] = len(cfg["CacheBehaviors"]["Items"])
    cfg["DefaultRootObject"] = ""
    cf.update_distribution(Id=d["Id"], IfMatch=r["ETag"], DistributionConfig=cfg)
    print("revertido: la raíz vuelve al dashboard Streamlit (recuerda quitar --server.baseUrlPath en la EC2)")


if __name__ == "__main__":
    {"configurar": configurar, "subir": subir, "revertir": revertir}.get(
        (sys.argv[1:] or [""])[0], lambda: sys.exit(__doc__))()
