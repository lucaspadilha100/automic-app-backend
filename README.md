# AutomIQ Booking Backend

> SaaS white label multi-tenant de agendamento — FastAPI + PostgreSQL + SQLAlchemy

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [Início Rápido](#início-rápido)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Rotas da API](#rotas-da-api)
- [Multi-Tenancy](#multi-tenancy)
- [Motor de Disponibilidade](#motor-de-disponibilidade)
- [Sistema de Pacotes](#sistema-de-pacotes)
- [Planos e Limites](#planos-e-limites)
- [Feature Flags](#feature-flags)
- [Auditoria e CRM](#auditoria-e-crm)
- [Webhooks](#webhooks)
- [Notificações](#notificações)
- [Migrations](#migrations)
- [Testes](#testes)
- [Deploy](#deploy)

---

## Visão Geral

O **AutomIQ Booking Backend** é uma API REST completa para gestão de agendamentos white label. Cada empresa (tenant) opera de forma totalmente isolada, com sua própria URL pública (`/public/{slug}`), painel administrativo, profissionais, serviços, pacotes de sessões e configurações visuais personalizadas.

### Papéis de usuário

| Papel | Acesso |
|---|---|
| `super_admin` | Console Master — gerencia todos os tenants, planos e features |
| `tenant_owner` | Proprietário da empresa — acesso total ao tenant |
| `manager` | Gerente — acesso ao painel, relatórios, configurações |
| `receptionist` | Recepcionista — agendamentos e clientes |
| `professional` | Profissional — vê apenas seus próprios agendamentos |
| `customer` | Cliente — agenda pela página pública |

---

## Arquitetura

```
┌─────────────────────────────────────────┐
│             FastAPI App                 │
│                                         │
│  /api/v1/public/{slug}  (sem auth)      │
│  /api/v1/auth           (login/tokens)  │
│  /api/v1/*              (painel admin)  │
│  /api/v1/master/*       (super_admin)   │
└──────────────┬──────────────────────────┘
               │
       ┌───────▼────────┐
       │   Services     │  (regras de negócio)
       │  appointment   │
       │  availability  │
       │  package       │
       │  plan_limit    │
       │  feature_flag  │
       │  notification  │
       │  webhook       │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │  SQLAlchemy    │
       │  PostgreSQL    │
       └────────────────┘
```

---

## Stack

- **Python 3.12** + **FastAPI 0.111**
- **SQLAlchemy 2.0** (ORM síncrono)
- **PostgreSQL 16** (banco principal)
- **Alembic** (migrations)
- **Pydantic v2** (validação)
- **python-jose** (JWT RS256)
- **passlib[bcrypt]** (hash de senhas)
- **pytz** (timezones)
- **pytest** (testes)

---

## Estrutura de Pastas

```
automiq-backend/
├── app/
│   ├── api/routes/          # Endpoints FastAPI
│   │   ├── auth.py          # Login/refresh interno
│   │   ├── customer_auth.py # Login/refresh cliente
│   │   ├── master_tenants.py# Console master (super_admin)
│   │   ├── appointments.py  # CRUD agendamentos + ações
│   │   ├── availability.py  # Consulta de slots
│   │   ├── customers.py     # CRUD clientes + notas + tags
│   │   ├── services.py      # CRUD serviços e categorias
│   │   ├── professionals.py # CRUD profissionais + agenda
│   │   ├── packages.py      # CRUD pacotes
│   │   ├── payments.py      # Registro de pagamentos
│   │   ├── users.py         # CRUD usuários + convites
│   │   ├── settings.py      # Config do tenant
│   │   ├── dashboard.py     # Dashboard + relatórios
│   │   ├── units_waitlist.py# Unidades + lista de espera
│   │   ├── resources.py     # Recursos físicos
│   │   ├── media.py         # Upload de arquivos
│   │   ├── audit.py         # Logs de auditoria
│   │   ├── notifications.py # Logs de notificações
│   │   └── public.py        # Página pública de agendamento
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── security.py      # JWT + bcrypt
│   │   ├── dependencies.py  # Injeção de dependências
│   │   ├── exceptions.py    # Exceções com códigos padronizados
│   │   ├── error_handlers.py# Handlers globais
│   │   ├── pagination.py    # Parâmetros de paginação
│   │   └── responses.py     # Formatos de resposta
│   ├── models/              # Modelos SQLAlchemy
│   ├── schemas/             # Schemas Pydantic
│   ├── services/            # Lógica de negócio
│   └── main.py              # App FastAPI + routers
├── db/
│   ├── base.py              # DeclarativeBase
│   └── session.py           # Engine + SessionLocal
├── alembic/                 # Migrations
├── tests/
│   ├── unit/                # Testes unitários
│   └── integration/         # Testes de integração
├── scripts/
│   └── seed.py              # Dados iniciais
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── Makefile
```

---

## Início Rápido

### Com Docker (recomendado)

```bash
git clone <repo>
cd automiq-backend

cp .env.example .env          # Ajuste se necessário
docker-compose up --build     # Sobe PostgreSQL + API + seed automático
```

A API estará disponível em `http://localhost:8000`  
Documentação Swagger: `http://localhost:8000/docs`

### Manual

```bash
# 1. Criar ambiente virtual
python -m venv venv && source venv/bin/activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar banco
createdb automiq_db
cp .env.example .env          # Editar DATABASE_URL

# 4. Rodar migrations
alembic upgrade head

# 5. Seed inicial
python scripts/seed.py

# 6. Iniciar servidor
uvicorn app.main:app --reload
```

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | — | URL completa do PostgreSQL |
| `SECRET_KEY` | gerado | Chave para assinar JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | Validade do access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Validade do refresh token |
| `BACKEND_CORS_ORIGINS` | `*` | Origens permitidas (CSV) |
| `ENVIRONMENT` | development | development / staging / production |
| `FIRST_SUPER_ADMIN_EMAIL` | admin@automiq.com.br | E-mail do primeiro admin |
| `FIRST_SUPER_ADMIN_PASSWORD` | AutomIQ@2024! | Senha do primeiro admin |
| `DEFAULT_TIMEZONE` | America/Sao_Paulo | Timezone padrão |
| `MAX_UPLOAD_SIZE_MB` | 10 | Tamanho máximo de upload |
| `WEBHOOKS_ENABLED` | false | Habilitar disparo de webhooks |

---

## Rotas da API

### Autenticação

```
POST   /api/v1/auth/login               # Login interno
POST   /api/v1/auth/refresh             # Renovar tokens
GET    /api/v1/auth/me                  # Usuário atual
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password

POST   /api/v1/customer-auth/register  # Cadastro de cliente
POST   /api/v1/customer-auth/login
POST   /api/v1/customer-auth/refresh
GET    /api/v1/customer-auth/me
```

### Página Pública (sem autenticação)

```
GET    /api/v1/public/{slug}                      # Info do tenant
GET    /api/v1/public/{slug}/services             # Serviços disponíveis
GET    /api/v1/public/{slug}/professionals        # Profissionais
GET    /api/v1/public/{slug}/availability         # Slots disponíveis
POST   /api/v1/public/{slug}/appointments         # Agendar (requer login cliente)
POST   /api/v1/public/{slug}/appointments/{id}/cancel
GET    /api/v1/public/{slug}/my-appointments      # Meus agendamentos
```

### Painel Administrativo

```
# Serviços
GET/POST       /api/v1/services
GET/PUT/DELETE /api/v1/services/{id}
GET/POST       /api/v1/services/categories
GET/PUT/DELETE /api/v1/services/categories/{id}

# Profissionais
GET/POST       /api/v1/professionals
GET/PUT/DELETE /api/v1/professionals/{id}
PUT            /api/v1/professionals/{id}/services   # Vincular serviços
PUT            /api/v1/professionals/{id}/availability

# Horários
PUT/GET        /api/v1/professionals/business-hours
GET/POST       /api/v1/professionals/blocked-times
DELETE         /api/v1/professionals/blocked-times/{id}

# Disponibilidade
GET            /api/v1/availability/slots?service_ids=&target_date=

# Agendamentos
GET/POST       /api/v1/appointments
GET            /api/v1/appointments/{id}
POST           /api/v1/appointments/{id}/confirm
POST           /api/v1/appointments/{id}/start
POST           /api/v1/appointments/{id}/complete
POST           /api/v1/appointments/{id}/cancel
POST           /api/v1/appointments/{id}/no-show
POST           /api/v1/appointments/{id}/reschedule
GET            /api/v1/appointments/{id}/status-history

# Clientes
GET/POST       /api/v1/customers
GET/PUT        /api/v1/customers/{id}
GET/POST       /api/v1/customers/{id}/notes
GET/POST       /api/v1/customers/{id}/procedures
GET            /api/v1/customers/{id}/appointments
GET/POST       /api/v1/customers/{id}/packages
GET/POST/DELETE /api/v1/customers/{id}/tags/{tag_id}

# Pacotes
GET/POST       /api/v1/packages
GET/PUT/DELETE /api/v1/packages/{id}
GET            /api/v1/packages/customer-packages/{id}
PATCH          /api/v1/packages/customer-packages/{id}/payment
POST           /api/v1/packages/customer-packages/{id}/cancel
GET            /api/v1/packages/customer-packages/{id}/sessions

# Pagamentos
GET/POST       /api/v1/payments/appointments/{appt_id}/payments
POST           /api/v1/payments/appointments/{appt_id}/payments/{pay_id}/refund
GET            /api/v1/payments/summary

# Usuários e convites
GET/PUT/DELETE /api/v1/users/{id}
GET/POST       /api/v1/users/invites
POST           /api/v1/users/invites/accept

# Configurações
GET            /api/v1/settings
PUT            /api/v1/settings/general
PUT            /api/v1/settings/theme
PUT            /api/v1/settings/booking-policy
GET/POST/PUT   /api/v1/settings/notifications
GET/POST/PUT/DELETE /api/v1/settings/webhooks

# Dashboard e Relatórios
GET            /api/v1/dashboard
GET            /api/v1/reports/appointments-by-status
GET            /api/v1/reports/revenue-by-professional
GET            /api/v1/reports/revenue-by-service
GET            /api/v1/reports/new-customers-over-time
GET            /api/v1/reports/occupancy-rate

# Unidades e Lista de espera
GET/POST/PUT/DELETE /api/v1/units
GET/POST       /api/v1/waitlist
PATCH          /api/v1/waitlist/{id}/status

# Recursos físicos
GET/POST/PUT/DELETE /api/v1/resources
POST/DELETE    /api/v1/resources/services/{id}/resources/{id}

# Mídia
POST           /api/v1/media/upload
GET            /api/v1/media
DELETE         /api/v1/media/{id}

# Auditoria
GET            /api/v1/audit-logs
GET            /api/v1/audit-logs/actions

# Notificações (logs)
GET            /api/v1/notifications/logs
```

### Console Master (super_admin)

```
GET/POST       /api/v1/master/tenants
GET/PUT        /api/v1/master/tenants/{id}
PATCH          /api/v1/master/tenants/{id}/status
GET/POST/PUT   /api/v1/master/plans
PUT            /api/v1/master/tenants/{id}/subscription
GET/PUT        /api/v1/master/tenants/{id}/limit-overrides
GET/PUT        /api/v1/master/tenants/{id}/features
PUT            /api/v1/master/tenants/{id}/settings
PUT            /api/v1/master/tenants/{id}/theme
GET            /api/v1/master/tenants/{id}/audit-logs
```

---

## Multi-Tenancy

O isolamento entre tenants é garantido por:

1. **Coluna `tenant_id`** em todas as tabelas — toda query filtra por tenant
2. **Dependência `require_active_tenant`** — valida status do tenant antes de cada operação
3. **Verificação de papel** — `get_current_tenant` bloqueia `super_admin` nas rotas de tenant
4. **Slug único** — cada tenant tem URL pública própria (`/public/{slug}`)

Status de tenant: `trial` → `active` → `suspended` / `cancelled` / `inactive`

---

## Motor de Disponibilidade

O serviço `AvailabilityService` calcula slots livres considerando:

1. **Horário de funcionamento** do tenant por dia da semana (`BusinessHour`)
2. **Agenda individual** do profissional (`ProfessionalAvailability`)
3. **Agendamentos existentes** com status ativos (`scheduled`, `confirmed`, `in_progress`, `pending_payment`)
4. **Bloqueios** de tenant e profissional (`BlockedTime`)
5. **Intervalos** (buffer_before + duration + buffer_after)
6. **Política de agendamento**: antecedência mínima, máximo de dias no futuro, intervalo entre slots
7. **Horário de almoço/descanso** (break_start/end_time)

Antes de criar um agendamento, o `validate_slot` usa `SELECT FOR UPDATE` para evitar condição de corrida (double booking).

---

## Sistema de Pacotes

Fluxo completo de sessões:

```
Package (definição: 10 sessões de drenagem)
  └── CustomerPackage (compra: cliente X, 10 sessões, R$ 350)
        └── PackageSession (cada uso)
              ├── reserved   → ao agendar
              ├── consumed   → ao completar agendamento
              ├── returned   → ao cancelar agendamento
              └── cancelled  → ao cancelar pacote
```

Validações automáticas:
- Status do pacote (`active` / `expired` / `cancelled`)
- Sessões restantes > 0
- Pagamento confirmado
- Serviço permitido no pacote
- Data de expiração

---

## Planos e Limites

Limites verificados ao criar recursos:

| Recurso | Verificado em |
|---|---|
| Serviços | `check_service_limit` |
| Profissionais | `check_professional_limit` |
| Usuários | `check_user_limit` |
| Pacotes | `check_package_limit` |
| Unidades | `check_unit_limit` |

A resolução de limite segue a ordem: **Override individual > Plano contratado > ilimitado (None)**

---

## Feature Flags

Features controladas por plano ou override manual:

| Feature Key | Descrição |
|---|---|
| `packages` | Pacotes de sessões |
| `multi_unit` | Múltiplas unidades |
| `waitlist` | Lista de espera |
| `advanced_reports` | Relatórios avançados |
| `physical_resources` | Recursos físicos |
| `webhooks` | Webhooks de eventos |
| `before_after_photos` | Fotos antes/depois |
| `crm_integration` | Integração CRM |
| `custom_terms` | Termos personalizados |
| `online_payment` | Pagamento online |

---

## Auditoria e CRM

**AuditLog** — registra toda ação relevante: quem, o quê, quando, valores antigos/novos.

**CustomerEvent** — bus de eventos do cliente para automações e integrações futuras:
`customer_created`, `appointment_created`, `appointment_completed`, `payment_confirmed`, etc.

---

## Webhooks

Quando habilitado (`WEBHOOKS_ENABLED=true`), o sistema dispara eventos para endpoints cadastrados:

```json
{
  "event": "appointment.created",
  "tenant_id": "...",
  "data": { ... }
}
```

A assinatura HMAC-SHA256 é enviada no header `X-AutomIQ-Signature`.  
Em produção: migrar `webhook_service.dispatch()` para tarefa assíncrona (Celery/ARQ).

---

## Notificações

Templates configuráveis por evento e canal (`whatsapp`, `email`, `sms`):

Variáveis disponíveis nos templates:
- `{{customer_name}}`, `{{professional_name}}`, `{{service_name}}`
- `{{appointment_date}}`, `{{appointment_time}}`
- `{{tenant_name}}`, `{{tenant_phone}}`

> Em produção: implementar os métodos `_send_whatsapp`, `_send_email`, `_send_sms` em `notification_service.py` com os providers de sua escolha (Z-API, Twilio, Resend, etc).

---

## Migrations

```bash
# Gerar migration automaticamente
make migrate-generate msg="add tabela X"

# Aplicar todas as migrations
make migrate

# Rollback 1 migration
make migrate-down

# Criar tabelas direto (sem Alembic, apenas dev)
make create-db
```

---

## Testes

```bash
# Todos os testes
make test

# Com cobertura
make test-cov

# Apenas unitários (sem banco)
pytest tests/unit/ -v

# Apenas integração (com banco)
pytest tests/integration/ -v
```

Resultado esperado (sem banco disponível): **44 passed, 1 skipped**

---

## Deploy

### Produção com Docker

```bash
docker build -t automiq-backend .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e SECRET_KEY=... \
  -e ENVIRONMENT=production \
  automiq-backend
```

### Checklist de Produção

- [ ] `SECRET_KEY` forte e único (min 32 chars)
- [ ] `ENVIRONMENT=production` (desabilita /docs e /redoc)
- [ ] `DATABASE_URL` com SSL (`?sslmode=require`)
- [ ] `BACKEND_CORS_ORIGINS` com domínios específicos
- [ ] Implementar providers de e-mail/WhatsApp/SMS
- [ ] Configurar task queue (Celery/ARQ) para webhooks e notificações
- [ ] Configurar storage S3/R2 para uploads
- [ ] Configurar reverse proxy (Nginx/Caddy) com HTTPS
- [ ] Monitoramento (Sentry, Datadog, etc)
- [ ] Backup automático do PostgreSQL

---

## Licença

Proprietário — AutomIQ © 2024. Todos os direitos reservados.

---

## Complemento de auditoria implementado

Esta versão inclui os ajustes de aderência ao prompt inicial apontados pela auditoria externa:

### Configurações de pagamento Pix manual

Novo recurso por tenant em `tenant_payment_settings`, acessível por:

- `GET /api/v1/settings/payment`
- `PUT /api/v1/settings/payment`

Campos principais:

- `require_deposit_by_default`
- `default_deposit_type` (`none`, `fixed`, `percentage`)
- `default_deposit_value`
- `require_deposit_for_first_appointment`
- `require_deposit_after_no_show`
- `manual_payment_instructions`
- `pix_key`

Não há gateway Asaas/Mercado Pago nesta etapa. O objetivo é suportar sinal/Pix manual e confirmação operacional.

### Políticas de no-show

`tenant_booking_policies` recebeu:

- `no_show_limit_before_deposit_required`
- `auto_require_deposit_after_no_show`
- `consume_package_session_on_no_show`

### Pacotes com tabela relacional

Além do campo legado `packages.service_ids`, foi criada a tabela `package_services` para integridade referencial.

Endpoints:

- `GET /api/v1/packages/{package_id}/services`
- `POST /api/v1/packages/{package_id}/services`
- `DELETE /api/v1/packages/{package_id}/services/{service_id}`

O payload antigo `service_ids` continua compatível.

### Campos de pacote no agendamento

- `appointments.uses_package`
- `appointment_services.package_session_id`

### Unidades

`units` agora possui `whatsapp` opcional.

### Estruturas futuras

Foram adicionadas estruturas básicas para:

- `appointment_reviews`
- `coupons`
- `appointment_holds`

Rotas principais:

- `GET /api/v1/reviews`
- `GET/POST /api/v1/appointments/{appointment_id}/reviews`
- `GET/POST /api/v1/coupons`
- `GET/PUT/PATCH /api/v1/coupons/{coupon_id}`
- `POST /api/v1/appointment-holds`
- `GET /api/v1/appointment-holds/{hold_id}`
- `POST /api/v1/appointment-holds/{hold_id}/cancel`

### Portal do cliente final

Novos endpoints:

- `GET /api/v1/customer/me`
- `PUT /api/v1/customer/me`
- `GET /api/v1/customer/tenants/{slug}/profile`
- `PUT /api/v1/customer/tenants/{slug}/profile`
- `GET /api/v1/customer/tenants/{slug}/appointments`
- `GET /api/v1/customer/tenants/{slug}/appointments/{appointment_id}`
- `POST /api/v1/customer/tenants/{slug}/appointments/{appointment_id}/cancel`
- `POST /api/v1/customer/tenants/{slug}/appointments/{appointment_id}/reschedule`
- `GET /api/v1/customer/tenants/{slug}/packages`
- `GET /api/v1/customer/tenants/{slug}/packages/{customer_package_id}`
- `GET /api/v1/customer/tenants/{slug}/procedure-history`

Esses endpoints filtram por cliente autenticado e tenant público acessado.

### Organização de código

Foram adicionados:

- `app/repositories/`
- services faltantes: `payment_service.py`, `media_service.py`, `invite_service.py`, `booking_policy_service.py`, `customer_timeline_service.py`, `unit_service.py`
- schemas separados por domínio, mantendo compatibilidade com `schemas.py`

### Migration incremental

Nova migration:

```bash
alembic upgrade head
```

Arquivo:

- `alembic/versions/0002_audit_gap_fixes.py`

### Validação

O `scripts/validate_backend.py` foi atualizado para checar as novas tabelas, colunas, rotas e arquivos.

Comandos recomendados:

```bash
alembic upgrade head
python scripts/seed.py
python -m pytest tests/ -v
python scripts/validate_backend.py
```

---

## Complemento de alinhamento ao prompt inicial — Maio/2026

Esta versão inclui uma rodada adicional de correções para alinhar o backend ao prompt inicial e à auditoria visual de código.

### Correções adicionadas

- Portal do cliente final com responses seguros para evitar exposição de `internal_notes`.
- Correção de criação de avaliações pós-atendimento com `customer_account_id` do cliente autenticado.
- `package_sessions.status` compatível com a spec (`reserved`, `used`, `cancelled`), mantendo `action` legado para compatibilidade.
- `customer_packages.purchase_price` e `customer_packages.created_by_user_id`, mantendo `price_paid` legado.
- Status de pacote compatível com `fully_used`, mantendo `completed` legado para compatibilidade.
- `tenant_booking_policies.consume_package_session_on_no_show` aplicado no fluxo real de no-show.
- `unit_id` opcional em `professionals`, `resources` e `business_hours`.
- `tenant_id` em `customer_tag_links` para facilitar validação multi-tenant direta.
- Campos compatíveis com a spec em `customer_notes`: `note` e `visibility`.
- Campos compatíveis com a spec em `appointment_status_history`: `old_status`, `new_status`, `changed_by_user_id`, `changed_by_customer_id`.
- Tabela global `theme_presets` com presets iniciais: `estetica_premium`, `barbearia_dark`, `salao_clean`, `clinica_minimalista`, `spa_natural`, `lash_brow_feminino`.
- Seed atualizado para os planos `Start`, `Pro` e `Premium`.
- Rate limiting simples em memória nos endpoints de login interno e login de cliente final.
- Migration incremental `0003_prompt_alignment_fixes.py`.

### Observações de compatibilidade

Alguns campos antigos foram mantidos para não quebrar endpoints, testes e payloads existentes:

- `CustomerPackage.price_paid` continua existindo junto com `purchase_price`.
- `PackageSession.action` continua existindo junto com `status`.
- `CustomerNote.content` e `is_internal` continuam existindo junto com `note` e `visibility`.
- `AppointmentStatusHistory.from_status/to_status` continuam existindo junto com `old_status/new_status`.

### Validação recomendada

Após extrair o pacote, rode:

```bash
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
python -m pytest tests/ -v
python scripts/validate_backend.py
```

Se for usar Docker:

```bash
docker-compose up --build
```

---

## Fechamento final de aderência ao prompt inicial

Esta versão inclui a rodada final de ajustes visuais/estruturais do prompt inicial:

- `appointment_holds` corrigido para criação administrativa sem referência inválida a cliente autenticado.
- Todo tenant criado pelo Console Master passa a receber configurações padrão, `TenantPaymentSettings`, unidade principal e assinatura padrão no plano `Start`, quando o plano existir.
- A primeira unidade do tenant pode ser criada mesmo sem `multi_unit`; novas unidades continuam controladas por feature flag e limite de plano.
- Tags e notas do cliente foram alinhadas ao prompt com `tenant_id`, `note` e `visibility`, mantendo compatibilidade com os campos legados.
- Services antes vazios agora possuem lógica reutilizável para mídia, convites, timeline do cliente e unidades.
- Console Master possui endpoints GET para detalhe de plano, settings e tema.
- Migration incremental `0004_final_prompt_closure.py` realiza backfill de aliases e cria dados padrão faltantes para tenants existentes.

Após extrair o projeto, rode:

```bash
alembic upgrade head
python scripts/seed.py
python -m pytest tests/ -v
python scripts/validate_backend.py
```

---

## Módulo: Terms and Consents

Gerenciamento profissional de Termos e Consentimentos por tenant. Cobre:
termos gerais, política de privacidade, autorização de imagem, termos de procedimento,
orientações pós-procedimento e aceite formal do cliente.

### Tabelas criadas (migration `0005_add_terms_and_acceptances`)

| Tabela | Descrição |
|---|---|
| `tenant_terms` | Documentos de termos por tenant (title, content, term_type, version, is_active) |
| `customer_term_acceptances` | Registro de aceite por cliente (term_id, customer_account_id, tenant_customer_id, accepted_at, ip_address, user_agent) |

`term_type` aceita: `general`, `procedure`, `image_authorization`, `privacy_policy`, `post_procedure`.

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/terms` | Lista termos do tenant (filtros: `term_type`, `is_active`) |
| `POST` | `/api/v1/admin/terms` | Cria novo termo |
| `GET` | `/api/v1/admin/terms/{term_id}` | Detalha termo |
| `PUT` | `/api/v1/admin/terms/{term_id}` | Atualiza termo |
| `PATCH` | `/api/v1/admin/terms/{term_id}/status` | Ativa/inativa termo |

### Endpoints do portal do cliente

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/customer/tenants/{slug}/terms` | Lista termos ativos do tenant |
| `POST` | `/api/v1/customer/tenants/{slug}/terms/{term_id}/accept` | Aceita termo (registra ip, user_agent, gera evento) |

### Eventos gerados

- **`customer_event`** `term_accepted` — emitido quando cliente aceita um termo. Metadata: `term_type`, `version`, `title`.
- **`audit_log`** `term_created`, `term_updated`, `term_activated`, `term_deactivated` — emitido em todas as ações administrativas sobre termos.

### Comandos

```bash
# Aplicar migration
alembic upgrade head

# Rodar testes
python -m pytest tests/ -v

# Validar backend completo
python scripts/validate_backend.py
```

---

## Módulo: Procedure Photos / Before-After Photos

Gerenciamento profissional de fotos antes/depois/progresso vinculadas ao histórico de procedimento (`procedure_history`). Suporta controle de visibilidade interno vs. cliente final.

### Relação com media_files e procedure_history

Cada `ProcedurePhoto` referencia:
- `media_file_id` → `media_files.id` (arquivo físico já armazenado)
- `procedure_history_id` → `procedure_history.id` (histórico ao qual a foto pertence)
- `service_id` (opcional) → `services.id` (serviço/procedimento específico)

A remoção de uma foto remove **apenas o vínculo** `procedure_photos` — o `media_file` físico é preservado.

### Tabela criada (migration `0006_add_procedure_photos`)

| Tabela | Descrição |
|---|---|
| `procedure_photos` | Vínculo entre media_file e procedure_history com photo_type e visibility |

**`photo_type`**: `before`, `after`, `progress`

**`visibility`**: `internal` (só admin/profissional), `customer_visible` (também visível ao cliente)

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/procedure-history/{procedure_id}/photos` | Lista todas as fotos (internal + customer_visible) |
| `POST` | `/api/v1/admin/procedure-history/{procedure_id}/photos` | Cria vínculo de foto ao histórico |
| `GET` | `/api/v1/admin/procedure-history/{procedure_id}/photos/{photo_id}` | Detalha foto específica |
| `PUT` | `/api/v1/admin/procedure-history/{procedure_id}/photos/{photo_id}` | Atualiza photo_type, visibility, caption, service_id |
| `DELETE` | `/api/v1/admin/procedure-history/{procedure_id}/photos/{photo_id}` | Remove vínculo (não deleta media_file) |

### Endpoint do portal do cliente

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/customer/tenants/{slug}/procedure-history/{procedure_id}/photos` | Lista somente fotos `customer_visible` do próprio cliente |

Fotos `internal` **nunca** são retornadas ao cliente final.

### Eventos gerados

- **`audit_log`** `procedure_photo_added`, `procedure_photo_updated`, `procedure_photo_removed` — em todas as ações administrativas.
- **`customer_event`** `procedure_photo_added` — emitido **somente** quando `visibility = customer_visible`. Metadata: `photo_type`, `procedure_history_id`, `media_file_id`, `service_id`.

### Comandos

```bash
# Aplicar migration
alembic upgrade head

# Rodar testes
python -m pytest tests/ -v

# Validar backend completo
python scripts/validate_backend.py
```

---

## Módulo: Professional Commissions

Configuração e geração automática de comissões por profissional ao concluir atendimentos.

### Tabelas criadas (migration `0007_add_professional_commissions`)

| Tabela | Descrição |
|---|---|
| `professional_commission_settings` | Configuração de comissão por profissional (type, value, is_active) |
| `commission_records` | Registro de comissão gerado ao concluir appointment |

**`commission_type`**: `percentage` (% sobre total), `fixed` (valor fixo), `none` (não gera registro)

**`status`**: `pending` → `paid` ou `cancelled`

### Cálculo de comissão

| Tipo | Fórmula |
|---|---|
| `percentage` | `appointment.total_price × commission_value / 100` |
| `fixed` | `commission_value` (valor direto) |
| `none` | Nenhum `commission_record` criado |

### Geração automática

Ao concluir um appointment (`status = completed`), o sistema chama `CommissionService.generate_for_appointment()` automaticamente. Regras:
- Busca configuração ativa para o profissional do appointment
- Não cria registro se não houver configuração ou se `commission_type = none`
- Idempotente: não duplica registro para o mesmo `appointment_id + professional_id`

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/commissions/settings` | Lista configurações do tenant |
| `POST` | `/api/v1/admin/commissions/settings` | Cria configuração |
| `GET` | `/api/v1/admin/commissions/settings/{id}` | Detalha configuração |
| `PUT` | `/api/v1/admin/commissions/settings/{id}` | Atualiza configuração |
| `PATCH` | `/api/v1/admin/commissions/settings/{id}/status` | Ativa/inativa |
| `GET` | `/api/v1/admin/commissions/records` | Lista registros (filtros: professional_id, status) |
| `GET` | `/api/v1/admin/commissions/records/{id}` | Detalha registro |
| `POST` | `/api/v1/admin/commissions/records/{id}/mark-paid` | Marca como pago |
| `POST` | `/api/v1/admin/commissions/records/{id}/cancel` | Cancela |

Todas as ações de criação, edição, ativação, pagamento e cancelamento geram `audit_log`. Comissões não são expostas no portal do cliente final.

---

## Módulo: Custom Forms / Anamnesis Forms

Formulários personalizados por tenant para anamnese, pré-atendimento, pós-atendimento e avaliação, com campos configuráveis e respostas em JSONB.

### Tabelas criadas (migration `0008_add_custom_forms`)

| Tabela | Descrição |
|---|---|
| `custom_forms` | Formulário com title, form_type, is_active |
| `custom_form_fields` | Campos do formulário (label, field_type, required, options JSONB, sort_order) |
| `custom_form_responses` | Respostas submetidas pelo cliente (answers JSONB, submitted_at) |

**`form_type`**: `anamnesis`, `pre_service`, `post_service`, `evaluation`

**`field_type`**: `text`, `textarea`, `number`, `date`, `boolean`, `select`, `multiselect`

Campos `select` e `multiselect` exigem `options` (lista de strings). Respostas são validadas contra `required` e `options` permitidas no momento do submit.

### Feature flag

Feature key: `custom_forms` — obrigatória nos endpoints admin e no portal do cliente. Se desativada, retorna `FEATURE_DISABLED (403)`.

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/forms` | Lista formulários (filtros: form_type, is_active) |
| `POST` | `/api/v1/admin/forms` | Cria formulário |
| `GET` | `/api/v1/admin/forms/{form_id}` | Detalha formulário com campos |
| `PUT` | `/api/v1/admin/forms/{form_id}` | Atualiza formulário |
| `PATCH` | `/api/v1/admin/forms/{form_id}/status` | Ativa/inativa |
| `POST` | `/api/v1/admin/forms/{form_id}/fields` | Adiciona campo |
| `PUT` | `/api/v1/admin/forms/{form_id}/fields/{field_id}` | Atualiza campo |
| `DELETE` | `/api/v1/admin/forms/{form_id}/fields/{field_id}` | Remove campo |
| `GET` | `/api/v1/admin/forms/{form_id}/responses` | Lista respostas |
| `GET` | `/api/v1/admin/forms/responses/{response_id}` | Detalha resposta |

### Endpoints do portal do cliente

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/customer/tenants/{slug}/forms` | Lista formulários ativos |
| `GET` | `/api/v1/customer/tenants/{slug}/forms/{form_id}` | Detalha formulário ativo com campos |
| `POST` | `/api/v1/customer/tenants/{slug}/forms/{form_id}/submit` | Submete resposta |

### Eventos gerados

- **`audit_log`** `custom_form_created`, `custom_form_updated`, `custom_form_activated/deactivated`, `custom_form_field_added`, `custom_form_field_updated`, `custom_form_field_deleted`
- **`customer_event`** `form_submitted` — emitido ao submeter resposta. Metadata: `form_type`, `title`.

### Comandos

```bash
alembic upgrade head
python -m pytest tests/ -v
python scripts/validate_backend.py
```

---

## Módulo: Customer Lifecycle

Controle automático do ciclo de vida do cliente dentro de cada tenant — identifica clientes novos, ativos, recorrentes, em risco, inativos e VIP para apoiar CRM, reativação e segmentação.

### Campos adicionados em `tenant_customers` (migration `0009_add_customer_lifecycle`)

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `lifecycle_status` | enum | `new` | Status atual: `new`, `active`, `recurring`, `at_risk`, `inactive`, `vip` |
| `last_appointment_at` | datetime | null | Data do último atendimento concluído |
| `next_appointment_at` | datetime | null | Data do próximo agendamento ativo |
| `total_spent` | numeric | 0 | Total gasto no tenant (nunca negativo) |
| `appointments_count` | int | 0 | Total de atendimentos concluídos (nunca negativo) |
| `no_show_count` | int | 0 | Total de no-shows (nunca negativo) |

### Tabela de configuração por tenant

`tenant_lifecycle_settings` — thresholds configuráveis por tenant:

| Campo | Padrão | Descrição |
|---|---|---|
| `inactive_after_days` | 90 | Dias sem retorno para tornar-se inativo |
| `at_risk_after_days` | 45 | Dias sem retorno para tornar-se em risco |
| `recurring_min_appointments` | 3 | Mín. atendimentos para tornar-se recorrente |
| `vip_min_appointments` | 5 | Mín. atendimentos para tornar-se VIP |
| `vip_min_total_spent` | 1000 | Mín. gasto para tornar-se VIP |

### Regras de atualização automática

O `CustomerLifecycleService` é chamado automaticamente pelo `AppointmentService` em 4 momentos:

| Evento | Ação de lifecycle |
|---|---|
| Appointment criado | Recalcula `next_appointment_at` e pode ativar cliente `new` |
| Appointment concluído | Atualiza `last_appointment_at`, incrementa `appointments_count`, atualiza `total_spent`, recalcula status |
| Appointment cancelado | Recalcula `next_appointment_at` e status |
| Appointment no_show | Incrementa `no_show_count`, recalcula status |

### Feature flag

Feature key: `customer_lifecycle` — obrigatória nos endpoints administrativos. A atualização automática dos campos continua ocorrendo independentemente da flag para manter dados consistentes.

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/customer-lifecycle/summary` | Contagem de clientes por lifecycle_status |
| `GET` | `/api/v1/admin/customer-lifecycle/customers` | Lista clientes com filtros por status, gasto, no_show |
| `GET` | `/api/v1/admin/customer-lifecycle/settings` | Configuração de thresholds do tenant |
| `PUT` | `/api/v1/admin/customer-lifecycle/settings` | Atualiza configuração (gera audit_log) |
| `POST` | `/api/v1/admin/customer-lifecycle/recalculate-all` | Recalcula lifecycle de todos os clientes |
| `GET` | `/api/v1/admin/customers/{id}/lifecycle` | Detalhe de lifecycle de um cliente |
| `POST` | `/api/v1/admin/customers/{id}/lifecycle/recalculate` | Recalcula lifecycle de um cliente (gera audit_log) |

### Eventos gerados

- **`customer_event`** `customer_lifecycle_updated` — emitido automaticamente quando `lifecycle_status` muda. Metadata: `previous_status`, `new_status`.
- **`audit_log`** `lifecycle_settings_updated`, `lifecycle_manual_recalculate` — em ações administrativas manuais.

### Uso futuro

Os campos de lifecycle são a base para: campanhas de reativação de clientes inativos, identificação de clientes VIP para tratamento diferenciado, alertas de clientes em risco, dashboards de CRM e segmentação avançada.

### Comandos

```bash
alembic upgrade head
python -m pytest tests/ -v
python scripts/validate_backend.py
```

---

## Módulo: Internal Automation Rules

Automações internas por tenant acionadas por eventos do sistema (`customer_events`). Permitem adicionar tags, criar notas, emitir webhooks e criar notification logs automaticamente sem intervenção manual.

### Tabela criada (migration `0010_add_automation_rules`)

`automation_rules` — campos: `name`, `trigger_event`, `conditions` (JSONB), `action_type`, `action_config` (JSONB), `is_active`.

### Trigger events suportados

Qualquer `event_type` gerado pelo sistema: `appointment_completed`, `appointment_no_show`, `form_submitted`, `customer_lifecycle_updated`, `payment_confirmed`, `package_sold`, etc.

### Conditions (JSONB)

Comparação por igualdade simples. Exemplos:

```json
{"metadata.lifecycle_status": "at_risk"}
{"entity_type": "tenant_customer"}
{"metadata.form_type": "anamnesis"}
```

Chaves com prefixo `metadata.` buscam dentro de `event.metadata`. Demais chaves (`event_type`, `entity_type`, `customer_account_id`, `tenant_customer_id`) comparam com o evento diretamente. Conditions vazias ou `null` executam para qualquer evento do tipo configurado.

### Ações disponíveis (`action_type`)

| Tipo | `action_config` | Comportamento |
|---|---|---|
| `add_customer_tag` | `{"tag_id": "uuid"}` | Aplica tag ao cliente (idempotente) |
| `create_customer_note` | `{"note": "texto", "visibility": "internal"}` | Cria nota de sistema no cliente |
| `emit_webhook_event` | `{"event_type": "automation_triggered"}` | Cria `WebhookDelivery` para endpoints ativos |
| `create_notification_log` | `{"channel": "internal", "event_type": "..."}` | Cria `NotificationLog` |

### Integração com CustomerEventService

Após cada `customer_event_service.emit()`, o `AutomationService.process_customer_event()` é chamado automaticamente. Falhas em automações são capturadas com `try/except` — **nunca quebram o fluxo original**.

### Feature flag

Feature key: `automation_rules` — obrigatória nos endpoints administrativos e na execução automática.

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/automations` | Lista regras (filtros: trigger_event, action_type, is_active) |
| `POST` | `/api/v1/admin/automations` | Cria regra |
| `GET` | `/api/v1/admin/automations/{id}` | Detalha regra |
| `PUT` | `/api/v1/admin/automations/{id}` | Atualiza regra |
| `PATCH` | `/api/v1/admin/automations/{id}/status` | Ativa/inativa |
| `DELETE` | `/api/v1/admin/automations/{id}` | Remove regra |

Todas as ações geram `audit_log`.

### Comandos

```bash
alembic upgrade head
python -m pytest tests/ -v
python scripts/validate_backend.py
```

---

## Módulo: WhatsApp / n8n Integration Settings

Configuração de integração WhatsApp/n8n por tenant. Este módulo armazena e gerencia as configurações de conexão, permitindo que automações futuras enviem mensagens via n8n sem implementar o envio real no MVP.

> **Limitação MVP**: este módulo **não envia mensagens WhatsApp reais**. Apenas configura e armazena os parâmetros de integração.

### Tabela criada (migration `0011_add_whatsapp_settings`)

`tenant_whatsapp_settings` — uma linha por tenant (unique em `tenant_id`):

| Campo | Descrição |
|---|---|
| `enabled` | Integração ativa? (default: false) |
| `provider` | Provedor: `n8n`, `evolution_api`, `zapi`, `meta`, `other` |
| `connection_type` | Tipo: `webhook`, `api_key`, `qr_code`, `manual` |
| `webhook_url` | URL do webhook n8n (validada como URL) |
| `instance_id` | ID da instância no provedor |
| `status` | `disconnected`, `connected`, `waiting_qr`, `error` |
| `last_connected_at` | Preenchido automaticamente ao status → `connected` |

### Feature flag

Feature key: `whatsapp_integration` — obrigatória em todos os endpoints administrativos.

### Endpoints administrativos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/admin/integrations/whatsapp` | Retorna configuração completa (cria padrão se não existir) |
| `PUT` | `/api/v1/admin/integrations/whatsapp` | Cria ou atualiza configuração |
| `GET` | `/api/v1/admin/integrations/whatsapp/status` | Retorna status resumido |
| `PATCH` | `/api/v1/admin/integrations/whatsapp/status` | Atualiza status |

Todas as alterações geram `audit_log`. Dados sensíveis (`webhook_url`, `instance_id`) **não são registrados** no audit_log.

### Relação futura com n8n e automações

O campo `webhook_url` será usado futuramente pelo sistema para enviar eventos ao n8n, incluindo: `appointment_created`, `appointment_confirmed`, `appointment_cancelled`, `appointment_reminder_24h`, `appointment_completed`, `payment_pending`, `payment_confirmed`, `customer_lifecycle_updated`, `automation_triggered`.

A estrutura de `WebhookDelivery` já existente no projeto será o canal de entrega — este módulo apenas centraliza a configuração por tenant.

### Comandos

```bash
alembic upgrade head
python -m pytest tests/ -v
python scripts/validate_backend.py
```

---

## Camada Comercial — Planos, Overrides de Feature, Preço Customizado e MRR

A camada comercial transforma o Console Master numa ferramenta real de operação de SaaS:
permite o dono do AutomIQ definir planos padrão, ativar/desativar recursos individualmente
por tenant, customizar limites e negociar preços diferentes do tabelado, com cálculo de MRR
considerando o valor efetivo cobrado.

### Conceitos

- **Plano base** (`plans`): pacote padrão (`Starter` / `Pro` / `Premium`) com preço, limites e features padrão.
- **Override de feature** (`tenant_feature_flags`): liga ou desliga um recurso para um tenant específico.
  - Manual `true` → recurso liberado mesmo se o plano não inclui.
  - Manual `false` → recurso bloqueado mesmo se o plano inclui.
  - Sem registro → cai no padrão do plano.
- **Override de limite** (`tenant_limit_overrides`): substitui qualquer limite (`max_services`, `max_professionals`, `max_users`, `max_appointments_per_month`, `max_units`, `max_packages`).
- **Preço customizado** (`tenant_subscriptions.custom_price_monthly`): valor mensal negociado individualmente. Quando preenchido, sobrescreve `plans.price_monthly` no cálculo de MRR.
  - Não pode ser negativo (CHECK constraint + Pydantic validator).
  - `custom_price_reason` e `billing_notes` registram o contexto da negociação.
- **Configuração efetiva**: combinação resolvida — para cada feature e cada limite, o sistema retorna o valor atual e a `source` (`plan` ou `manual_override`).

### Planos padrão semeados

| Plano | Preço/mês | Pacotes | Termos | Fotos B/A | Comissões | Anamnese | Lifecycle | Automation | WhatsApp | Pagto Online | Relatórios | CRM | Multi-unit | Espera | Recursos | Webhooks |
|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Starter** | R$ 97 | ✅ | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **Pro** | R$ 197 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | — | ✅ | — | — |
| **Premium** | R$ 347 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

Limites Starter: 20 serviços / 2 profissionais / 3 usuários / 300 agendamentos/mês.
Limites Pro: 100 serviços / 8 profissionais / 10 usuários / 2000 agendamentos/mês / 20 pacotes.
Limites Premium: 1000 serviços / 100 profissionais / 100 usuários / 20000 agendamentos/mês / 5 unidades / 1000 pacotes.

### Cálculo do preço efetivo e do MRR

```
effective_price_monthly =
    custom_price_monthly  se custom_price_monthly is not None
    plan.price_monthly    caso contrário
```

```
MRR = soma de effective_price_monthly de todos os tenants com status = 'active'
```

Tenants `trial`, `suspended`, `cancelled` e `inactive` **não somam** ao MRR — eles aparecem em
contadores separados em `/master/metrics/mrr`.

Exemplos:

- Plano Pro custa R$ 197. Tenant A no Pro sem `custom_price_monthly` → contribui R$ 197 ao MRR.
- Tenant B no Pro com `custom_price_monthly = 120` → contribui R$ 120 ao MRR.
- Tenant C no Starter (sem `before_after_photos` no plano) com `tenant_feature_flags(before_after_photos=true)` → recurso efetivo: ✅
- Tenant D no Premium (com `commissions` no plano) com `tenant_feature_flags(commissions=false)` → recurso efetivo: ❌

### Endpoints do Console Master

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/api/v1/master/tenants/{id}/effective-plan` | Visão consolidada: plano, assinatura, preço efetivo, features e limites efetivos com `source` |
| `PUT` | `/api/v1/master/tenants/{id}/subscription` | Troca plano e/ou define `custom_price_monthly`, `custom_price_reason`, `billing_notes`, `contracted_at` |
| `GET` | `/api/v1/master/tenants/{id}/features` | Mapa `{feature_key → {enabled, source}}` para todas as 15 features |
| `PUT` | `/api/v1/master/tenants/{id}/features` | Define override manual `enabled=true/false` para uma feature |
| `GET` | `/api/v1/master/tenants/{id}/limit-overrides` | Retorna overrides numéricos atuais |
| `PUT` | `/api/v1/master/tenants/{id}/limit-overrides` | Define overrides numéricos por limite |
| `GET` | `/api/v1/master/metrics/mrr` | MRR total, contagem por status, MRR por plano, ARPU, tenants com preço customizado |

#### Exemplo — `GET /master/tenants/{id}/effective-plan`

```json
{
  "tenant_id": "...",
  "plan": { "id": "...", "name": "Pro", "price_monthly": 197.0, "is_active": true },
  "subscription": {
    "id": "...",
    "status": "active",
    "custom_price_monthly": 120.0,
    "custom_price_reason": "Negociação especial",
    "billing_notes": "Cliente histórico",
    "effective_price_monthly": 120.0,
    "price_source": "manual_override",
    "contracted_at": "2026-04-01T00:00:00+00:00"
  },
  "features": {
    "packages":            { "enabled": true,  "source": "plan" },
    "before_after_photos": { "enabled": true,  "source": "manual_override" },
    "commissions":         { "enabled": false, "source": "manual_override" },
    "automation_rules":    { "enabled": false, "source": "plan" }
  },
  "limits": {
    "max_services":      { "value": 100, "source": "plan" },
    "max_professionals": { "value": 12,  "source": "manual_override" }
  }
}
```

### Auditoria

Toda alteração comercial é registrada em `audit_logs`:

| Action | Origem | Old/new |
|---|---|---|
| `subscription_updated` | PUT subscription (sempre) | snapshot completo antes/depois |
| `subscription_plan_changed` | PUT subscription quando `plan_id` muda | `plan_id` antigo → novo |
| `subscription_custom_price_updated` | PUT subscription quando `custom_price_monthly` muda | preço antigo → novo + reason |
| `feature_flag_updated` | PUT features | `feature_key`, `enabled` antigo → novo |
| `limit_override_changed` | PUT limit-overrides (uma por limite alterado) | `{limit_key: old}` → `{limit_key: new}` |
| `limit_override_updated` | PUT limit-overrides (resumo) | snapshot completo |

### Aplicação dos overrides nos módulos da Expansão 1

Os módulos sensíveis chamam `feature_flag_service.require_feature(...)` (que respeita o override
do tenant) — todos os endpoints administrativos retornam `FEATURE_DISABLED` quando o recurso
estiver desativado para aquele tenant, mesmo quando o plano original o inclui:

| Módulo | Feature key | Onde é checada |
|---|---|---|
| Termos e Consentimentos | `custom_terms` | Router `admin_terms` (dependency) |
| Fotos de Procedimento | `before_after_photos` | Router `admin_procedure_photos` (dependency) |
| Comissões de Profissionais | `commissions` | Router `admin_commissions` (dependency) |
| Anamnese / Custom Forms | `custom_forms` | Service `custom_form_service` |
| Customer Lifecycle | `customer_lifecycle` | Service `customer_lifecycle_service` (apenas endpoints administrativos — recálculo automático segue rodando para manter consistência) |
| Automation Rules | `automation_rules` | Service `automation_service` |
| WhatsApp/n8n | `whatsapp_integration` | Service `whatsapp_settings_service` |

### Migration

`alembic/versions/0012_add_commercial_overrides_and_mrr.py`:

- adiciona `plans.allow_commissions`
- adiciona `tenant_subscriptions.custom_price_monthly`, `custom_price_reason`, `billing_notes`, `contracted_at`
- adiciona CHECK `custom_price_monthly IS NULL OR custom_price_monthly >= 0`
- `down_revision = "0011_add_whatsapp_settings"`, com `downgrade()` funcional

### Comandos

```bash
alembic upgrade head
python scripts/seed.py
python -m pytest tests/ -v                  # 204 passed, 1 skipped
python scripts/validate_backend.py          # +13 commercial-layer checks
```
