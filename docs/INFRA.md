# Infraestructura — IntegrAI (Ivan)

> Responsable: Ivan (infraestructura AWS, Docs/PLAN.md §2). Complementa [`SEGURIDAD.md`](SEGURIDAD.md) y [`GOBIERNO_DATOS.md`](GOBIERNO_DATOS.md).
> El repo es público: aquí **no** van IDs de instancia, dominios ni secretos.

## 1. Decisión de arquitectura

| Entorno | Arquitectura | Motivo |
|---|---|---|
| **Demo (hackathon)** | Mantener la **EC2 `integra-server`** (Ubuntu 24.04) detrás de **CloudFront**: Streamlit en `:80` y API (`uvicorn`) en `:8000`. WhatsApp y el clasificador (ensemble) ya corren ahí. | Está operativo; migrar a serverless antes de la demo agrega riesgo sin beneficio. |
| **Producción (Integra)** | Camino **serverless** (AWS SAM): API Gateway + Lambda + SQS + DynamoDB + S3, según `SEGURIDAD.md` §Arquitectura. | Sin servidor que administrar, escala y trazabilidad; encaja con la ruta de datos de Integra. |

La demo **no** crea infraestructura serverless nueva: reutiliza lo que existe. El camino serverless queda documentado como plan (§6) para que Integra lo despliegue sin reescribir la lógica.

## 1.1 Demo RAG de la rama (no desplegada)

La rama `recomendador-rag` agrega un flujo estático para Pages: fuentes públicas `RAG/` → ingesta e índice léxico local ignorado → análisis determinístico → recomendador → JSON sintético → cola humana → ficha. No corre en la EC2 ni modifica CloudFront/WhatsApp. La integración backend, persistencia y RBAC son objetivos futuros.

## 2. Componentes y estado (auditado el 15-oct, tarde)

![Infraestructura TI: hoy vs. objetivo](img/infra_ti.png)

| Componente | Hoy | IaC |
|---|---|---|
| EC2 `integra-server` | En ejecución (`/opt/integra`) | No se recrea; se endurece (§4) |
| Security group | 80/8000 abiertos a `0.0.0.0/0`; 22/8501 a 1 IP | `infra/integra-server.yaml` (80/8000 solo desde CloudFront; 22/8501 sin ingreso) |
| Rol IAM de la instancia | Rol del escritorio Kiro (amplio) | `infra/integra-server.yaml` (mínimo privilegio) |
| CloudFront | ✅ Creado: `/` frontend React, `/streamlit*` Streamlit, API → :8000 · **sin WAF** | `tools/cloudfront_aws.py` (`crear`, `waf`, `auth-basica`) |
| Secretos (Meta + token API) | Parcial en Secrets Manager | `tools/secrets_aws.py`, `tools/desplegar_seguridad_ec2.sh` |
| Cifrado EBS | Cuenta con cifrado por defecto; volumen actual sin cifrar | `tools/ebs_aws.py` (plan; requiere detener la instancia) |
| Logs y alarmas | ❌ Sin configurar | `infra/integra-server.yaml` + `tools/cloudwatch_aws.py` |
| Respaldos EBS | ❌ Sin configurar | `infra/integra-server.yaml` + `tools/backup_aws.py` |
| Frontend (S3) | ✅ Bucket privado `integrai-frontend-<cuenta>` (BPA, cifrado, solo CloudFront vía OAC) | `tools/desplegar_frontend.py` |
| GitHub Pages | ❌ Workflow `pages.yml` falla: Pages no está activado en el repo | Activar en *Settings → Pages → GitHub Actions* |
| Stack CloudFormation | ❌ No desplegado | `infra/integra-server.yaml` (corregido en PR #14) |

## 3. Despliegue de la plantilla (por otra persona)

Requisitos: AWS CLI v2 con credenciales del evento, y el ID de la instancia.

```bash
aws cloudformation deploy \
  --template-file infra/integra-server.yaml \
  --stack-name integrai-server \
  --parameter-overrides \
      InstanceId=<id-de-integra-server> \
      VpcId=<vpc-de-la-instancia> \
      AlarmEmail=<correo-del-equipo> \
  --capabilities CAPABILITY_NAMED_IAM
```

Luego, en la EC2 (por SSM, ver `tools/ssm_push.py`):

```bash
sudo bash tools/desplegar_seguridad_ec2.sh   # token de la API desde Secrets Manager
sudo bash tools/endurecer_servicios_ec2.sh   # servicios sin root
```

Verificación: `python tools/seguridad_aws.py auditar`, `python tools/cloudwatch_aws.py auditar`
y `python tools/backup_aws.py auditar` → todo `OK`.

## 4. Endurecimiento del servidor

- **Security group**: ingreso 80/8000 **solo** desde el prefix list de CloudFront; sin SSH (administración por **SSM**). Lo aplica la plantilla y `tools/seguridad_aws.py corte`.
- **IAM mínimo**: `bedrock:InvokeModel` limitado a los modelos usados, `ssm:*` de sesión/parámetros y `secretsmanager:GetSecretValue` sobre `integrai/*`.
- **Sin root**: servicios `integra-webapi` e `integra` con `User=integra` (`tools/endurecer_servicios_ec2.sh`).
- **Despliegue trazable**: `/opt/integra` desde `git pull` de `main` (hoy se sube por SSM).

## 5. Observabilidad y respaldos

- **Log groups**: `/integra/app` (30 días) y `/integra/auditoria` (**2 años**, ver `GOBIERNO_DATOS.md` §4). Sin PII: los logs ya enmascaran teléfono y no guardan texto ni nombres.
- **Alarmas**: `StatusCheckFailed` de la instancia, `CPUUtilization` alta, mensajes visibles en la **DLQ**, y errores de Bedrock. Notifican a un topic SNS que se suscribe al correo del equipo.
- **Respaldos**: AWS Backup con plan diario sobre el volumen de la EC2 (retención corta; el dato sensible no se conserva más de lo necesario).

## 6. Camino serverless (futuro, Integra)

1. `GET`/`POST` del webhook → **API Gateway** + **Lambda** (firma, whitelist).
2. Encolar en **SQS** con **DLQ**; worker Lambda normaliza (Transcribe/visión) y clasifica con **Bedrock + Pydantic**.
3. Sesión y commit en **DynamoDB** (`TransactWriteItems`); medios en **S3** cifrado con lifecycle 24 h.
4. Secreto de Meta y token en **Secrets Manager**; **VPC endpoint** para Bedrock; **WAF** en API Gateway.
5. Empaquetado con **SAM** (`sam build --use-container` por `pydantic_core`) — ver `docs/PLAN.md` corrección 9.

## 7. Verificación

- `aws cloudformation describe-stacks --stack-name integrai-server` → `CREATE_COMPLETE`.
- Security group con 80/8000 desde el prefix list y sin 22/8501.
- Alarmas en estado `OK`/`INSUFFICIENT_DATA` (no `ALARM`) y suscripción de correo confirmada.
- `python tools/cloudwatch_aws.py auditar` y `python tools/backup_aws.py auditar` sin pendientes.
