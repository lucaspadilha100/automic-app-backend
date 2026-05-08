# AUTOMIC Backend — Mapa Completo do Sistema

Última atualização: 8 maio 2026 (após Expansão 5)

Esse documento é a referência única da verdade sobre o que existe no backend.
Quando Claude esquecer alguma feature, voltar aqui antes de inventar.

---

## RESUMO EXECUTIVO DO QUE EXISTE

### 21 migrations aplicadas
0001-0004: schema base (auth, tenant, agendamento)
0005: termos e aceites
0006: fotos de procedimento
0007: comissões de profissionais
0008: formulários customizados
0009: lifecycle de cliente (CRM básico)
0010: regras de automação
0011: configurações WhatsApp
0012: overrides comerciais + MRR
0013: platform settings (branding white-label)
0014: support tickets
0015: owner notifications
0016: documentos legais (ToS/Privacy)
0017: signup self-service (trial, terms)
0018: faturas dos tenants (billing)
0019: task runs (audit de jobs)
0020: billing_mode (manual/automatic/free)
0021: schedule exceptions + reschedule chain

### 35 modelos
appointment, audit, automation, base_model, commission, custom_form,
customer, customer_lifecycle, event, future, media, notification,
owner_notification, package, payment, plan, platform_document,
platform_settings, procedure, procedure_photo, professional, resource,
schedule, schedule_exception, service, support_ticket, task_run, tenant,
tenant_invoice, term, unit, user, waitlist, webhook, whatsapp

### 41 arquivos de rotas
### 40 services

---

## FUNCIONALIDADES POR ÁREA

### 1. AUTH (login/logout/permissões)
Endpoints `/auth/*`:
- POST /login, /refresh, /forgot-password, /reset-password
- GET /me

Roles: super_admin, tenant_owner, manager, professional, receptionist
Multi-tenant via JWT (tenant_id no token).

### 2. CADASTROS BÁSICOS DO TENANT (clínica)

**Unidades** (`/units`): clínica com várias filiais
- POST/GET/PUT/DELETE /units
- Lista de espera por unidade

**Profissionais** (`/professionals`):
- POST/GET/PUT/DELETE /professionals
- PUT /professionals/{id}/services (vínculo prof→serviço)
- PUT /professionals/{id}/availability (horários por weekday)

**Serviços** (`/services`):
- Categorias: POST/GET/PUT/DELETE /services/categories
- Serviços: POST/GET/PUT/DELETE /services
- Cada serviço tem: duração, buffer antes/depois, preço, requires_deposit

**Recursos físicos** (`/resources`): salas, equipamentos
- POST/GET/PUT/DELETE /resources
- Vínculo serviço↔recurso (ex: depilação requer "Sala 2")

**Clientes** (`/customers`):
- POST/GET/PUT /customers (cadastro)
- Notas internas, tags, procedimentos, agendamentos, pacotes
- Soft delete via deleted_at

### 3. AGENDA (núcleo do produto)

**Schedule do tenant** (`/schedule`):
- PUT/GET /schedule/business-hours (horário de funcionamento por dia)
- POST/GET/DELETE /schedule/blocked-times (bloqueios pontuais)

**Schedule Exceptions** (`/schedule-exceptions`) — Expansão 5:
- POST/GET/PATCH/DELETE /schedule-exceptions
- Tipos: holiday, leave (folga prof específico), closure (unidade fechada)
- POST /appointments/bulk-cancel (cancela em massa por janela)

**Availability** — endpoint mágico que você descreveu:
- GET /availability/slots (admin)
- GET /public/{slug}/availability (público, sem login)
- Considera: business_hours, professional_availability, schedule_exceptions, appointments, booking_policy
- Slot interval configurável (15/30/60 min), antecedência mínima, dias máximos

**Booking Policy** (parte de /settings/booking-policy):
- slot_interval_minutes (granularidade)
- min_minutes_before_booking (antecedência mínima)
- max_days_ahead_booking (limite de quanto à frente)
- allow_simultaneous_bookings

**Appointments** (`/appointments`):
- POST/GET /appointments (criar via painel)
- POST /{id}/confirm, /start, /complete, /cancel, /no-show, /reschedule
- GET /{id}/status-history
- Reschedule cria NOVO appointment + chain link (rescheduled_from_id ↔ rescheduled_to_id)
- Bulk cancel disponível em /appointments/bulk-cancel

### 4. PORTAL DO CLIENTE FINAL (paciente)

**Customer Auth** (`/customer-auth`):
- POST /register, /login, /refresh
- GET /me
- POST /forgot-password, /reset-password

**Booking público** (`/public/{slug}`) — sem login pra ver, com login pra agendar:
- GET /public/{slug} (landing da clínica)
- GET /public/{slug}/services (catálogo)
- GET /public/{slug}/professionals
- GET /public/{slug}/availability (slots livres)
- POST /public/{slug}/appointments (cliente agenda)
- POST /public/{slug}/appointments/{id}/cancel
- GET /public/{slug}/my-appointments

**Customer Portal mais avançado** (`/customer/...`):
- GET/PUT /customer/me (perfil global)
- GET/PUT /customer/tenants/{slug}/profile (perfil por clínica)
- GET /customer/tenants/{slug}/appointments
- POST /customer/tenants/{slug}/appointments/{id}/cancel
- POST /customer/tenants/{slug}/appointments/{id}/reschedule
- GET /customer/tenants/{slug}/packages (sessões compradas)
- GET /customer/tenants/{slug}/procedure-history (histórico)
- GET /customer/tenants/{slug}/forms (formulários)
- POST /customer/tenants/{slug}/forms/{id}/submit
- GET /customer/tenants/{slug}/terms (termos a aceitar)
- POST /customer/tenants/{slug}/terms/{id}/accept

### 5. PACOTES E SESSÕES

**Pacotes** (`/packages`):
- POST/GET/PUT/DELETE /packages
- Vincula serviços ao pacote
- POST /customer-packages (cliente compra pacote, recebe N sessões)
- PATCH /customer-packages/{id}/payment
- POST /customer-packages/{id}/cancel
- GET /customer-packages/{id}/sessions (quantas sessões usadas/restam)

### 6. PAGAMENTOS

**Pagamentos** (`/payments`):
- POST /appointments/{id}/payments (registrar pagamento)
- POST /appointments/{id}/payments/{id}/refund (reembolso)
- GET /summary (resumo financeiro)

**Configuração de pagamento** (`/settings/payment`):
- GET/PUT /settings/payment (chaves, depósito padrão)

### 7. PROCEDIMENTOS E HISTÓRICO MÉDICO

**Histórico de procedimentos**:
- Criados automaticamente quando appointment é completed
- Inclui anotações do profissional, data, serviços realizados

**Fotos de procedimento** (`/admin/procedure-history/{id}/photos`):
- POST/GET/PUT/DELETE fotos antes/depois
- Upload de mídia
- Visíveis no histórico do cliente

**Formulários customizados** (`/admin/forms`):
- POST/GET/PUT/DELETE forms
- Campos dinâmicos (texto, seleção, checkbox, etc)
- POST /admin/forms/{id}/fields
- Cliente preenche via portal: GET/POST /customer/tenants/{slug}/forms

### 8. COMISSÕES DE PROFISSIONAIS

**Comissões** (`/admin/commissions`):
- GET/POST/PUT /admin/commissions/settings
- Por profissional, fixo, %, ou misto
- Records: GET /records (cálculos automáticos)
- POST /records/{id}/mark-paid (marcou que pagou prof)
- POST /records/{id}/cancel

### 9. CRM / LIFECYCLE DO CLIENTE

**Customer lifecycle** (`/admin/customer-lifecycle`):
- GET/PUT /settings (regras de classificação: novo/ativo/inativo/perdido)
- GET /summary (quantos em cada estágio)
- GET /customers (lista filtrável)
- POST /recalculate-all (recalcula classificação de todos)
- GET /{id}/lifecycle (timeline do cliente: agendamentos, eventos, mudanças de stage)

### 10. AUTOMAÇÕES

**Regras de automação** (`/admin/automations`):
- GET/POST/PUT/DELETE /admin/automations
- Triggers: appointment_created, appointment_cancelled, customer_created, etc
- Actions: send WhatsApp, send email, change tag, etc
- PATCH /{id}/status (ativar/desativar)

### 11. NOTIFICAÇÕES

**Templates** (`/settings/notifications`):
- GET/POST/PUT (CRUD de templates por evento)
- Variáveis: {{customer_name}}, {{appointment_date}}, etc

**Logs** (`/notifications/logs`):
- GET (histórico de envios)

**Default templates built-in** (sem precisar criar):
- appointment_confirmed (email/sms/whatsapp)
- appointment_reminder_24h (email/sms/whatsapp)
- appointment_cancelled_bulk (whatsapp/email)
- tenant_welcome (email)
- invoice_due_3d, invoice_overdue, invoice_paid (email)

**Providers** (configuráveis via env):
- Mock (default, testa em memória)
- Resend (email) — RESEND_API_KEY + RESEND_LIVE=1
- Zenvia (SMS) — ZENVIA_API_KEY + ZENVIA_LIVE=1
- n8n (WhatsApp via webhook) — N8N_WEBHOOK_URL + N8N_LIVE=1
- Composite (mistura: email real + sms mock, etc)

**WhatsApp settings** (`/admin/integrations/whatsapp`):
- GET/PUT settings (token, instance)
- GET/PATCH /status (conectado, número)

### 12. WEBHOOKS

**Webhooks de saída** (`/settings/webhooks`):
- GET/POST/PUT/DELETE
- Eventos enviados: appointment_*, customer_*, payment_*

### 13. RELATÓRIOS / DASHBOARD

**Dashboard** (`/dashboard`):
- GET /dashboard (KPIs principais)
- GET /reports/appointments-by-status
- GET /reports/revenue-by-professional
- GET /reports/revenue-by-service
- GET /reports/new-customers-over-time
- GET /reports/occupancy-rate

### 14. AUDITORIA

**Audit logs** (`/audit-logs`):
- GET (histórico de alterações)
- GET /actions (lista de ações disponíveis)
- Captura: user_id, action, entity, old/new values, ip, user_agent, timestamp

### 15. MÍDIA / UPLOADS

**Media** (`/media`):
- POST /upload
- GET (lista)
- DELETE /{id}

### 16. CONFIGURAÇÕES / TEMA

**Settings** (`/settings`):
- GET / (geral)
- GET /effective-features (features ativas pro plano)
- GET /branding (logo, cores)
- PUT /general, /theme
- PUT /booking-policy

### 17. SUPORTE A CLIENTES (ticket)

**Tenant lado** (`/support/tickets`):
- GET/POST /support/tickets (cliente AUTOMIC abre ticket)
- GET /{id}, POST /{id}/messages

**Master lado** (`/master/support/tickets`):
- GET (você AUTOMIC vê todos)
- POST /messages, PATCH /status, /priority, /assign

### 18. USUÁRIOS / CONVITES INTERNOS

**Users** (`/users`):
- GET, GET /{id}, PUT /{id}, DELETE /{id}
- POST /invites (convidar funcionário pra equipe)
- POST /invites/accept
- GET /invites (lista pendentes)

### 19. TERMOS E ACEITES

**Termos** (`/admin/terms`):
- GET/POST/PUT /admin/terms
- PATCH /{id}/status
- Cliente assina via /customer/tenants/{slug}/terms

### 20. FUTURE (em uso parcial)

**Reviews** (`/reviews`, `/appointments/{id}/reviews`):
- GET (listar avaliações)
- POST (cliente avalia)

**Cupons** (`/coupons`):
- POST/GET/PUT
- PATCH /{id}/status

**Holds (reservas temporárias)** (`/appointment-holds`):
- POST (segurar slot por X minutos antes de confirmar)
- GET, POST /{id}/cancel

---

## ÁREA MASTER (você operando a plataforma)

### Tenants (`/master/tenants`):
- POST/GET/PUT (CRUD de tenants/clínicas)
- PATCH /{id}/status (ativar, suspender, cancelar)
- PUT /{id}/subscription (mudar plano, custom_price)
- GET/PUT /{id}/limit-overrides (limites custom)
- GET/PUT /{id}/features (features custom)
- GET /{id}/effective-plan (plano efetivo após overrides)
- GET/PUT /{id}/settings, /theme
- GET /{id}/audit-logs

### Plans (`/master/plans`):
- POST/GET/PUT
- Define: price, max_appointments, max_professionals, features

### Métricas (`/master/metrics`):
- GET /mrr (Monthly Recurring Revenue)

### Saúde dos tenants (`/master/health/tenants`):
- GET (lista com churn risk: critical/high/medium/low)

### Faturas dos tenants (`/master/invoices`):
- GET/GET/{id}
- POST /{id}/charge (gera link de pagamento via provider)
- POST /{id}/mark-paid
- POST /{id}/cancel

### Jobs de billing (`/master/jobs`):
- POST /generate-monthly-invoices
- POST /mark-overdue-invoices
- POST /enforce-billing
- POST /run-trial-expiration
- POST /send-24h-reminders

### Billing manual flexível (`/master/tenants/{id}/...`):
- POST /manual-payment (registrar Pix recebido fora do app)
- PATCH /billing-mode (manual/automatic/free)
- GET /billing-mode

### Notificações ao owner (`/master/notifications`):
- GET, GET /unread-count, PATCH /{id}/read, POST /mark-all-read
- Eventos: novo signup, novo ticket, fatura paga, etc

### Tasks audit (`/master/tasks`):
- GET (histórico de execuções de jobs com status, duração, summary)

### Plataforma — branding e docs (`/master/platform`):
- GET/PUT /settings (nome, logo, cores, contatos)
- GET /branding (resumo público)
- GET/PUT /documents/{type} (ToS, Privacy, etc)

### Operações (`/master`):
- POST /jobs/run-trial-expiration
- POST /jobs/send-24h-reminders
- GET /health/tenants

---

## INFRAESTRUTURA E OPERAÇÃO

### Health endpoints
- GET /health (200 sempre)
- GET /health/live (liveness probe)
- GET /health/ready (readiness — checa Postgres + Redis)
- GET /health/db
- GET /health/full

### Worker assíncrono (Arq + Redis)
- Cron horário: send_24h_reminders
- Cron diário: expire_trials, mark_overdue_invoices, enforce_billing
- Cron mensal: generate_monthly_invoices
- Tudo registra em TaskRun audit

### Logs estruturados
- LOG_FORMAT=json (prod) ou plain (dev)
- request_id, tenant_id, user_id em cada request
- access log automático por request

### Sentry (opcional)
- Setar SENTRY_DSN + pip install sentry-sdk[fastapi]
- No-op se DSN ausente

### Multi-tenancy
- JWT carrega tenant_id
- Todos os models tenant-scoped têm tenant_id obrigatório
- Filtros automáticos via require_active_tenant dep

### Rate limiting (configurável)
- Por IP (não por tenant ainda — pendência futura)
- Desabilitável via RATE_LIMIT_ENABLED=false

---

## QUE ESTÁ TESTADO

- 342 testes unitários verdes
- validate_backend.py 111/111 (E2E real contra Postgres)
- Smoke E2E manual em todas as expansões

---

## PENDÊNCIAS CONHECIDAS

1. **Frontend** — backend pronto, frontends pausados (master, tenant, público, portal cliente)
2. **Mercado Pago real** — skeleton ativável via env
3. **Seed.py** — não cria profissional/service no demo (precisa fixar pra facilitar testes)
4. **Rate limit por tenant** — hoje é só por IP
5. **Backups automáticos** — não configurado (precisa pg_dump + storage off-site)

---

## PRINCÍPIOS DO PROJETO (lembrar sempre)

- Multi-tenant: cada tenant isolado
- White-label: tenant pode customizar branding, mas operação é sua
- Default seguro: novos tenants billing_mode=manual, status=trial
- Skeletons ativáveis: Mercado Pago, Resend, Zenvia, n8n, Sentry — todos no-op até env setar
- Idempotência: jobs podem rodar duas vezes sem duplicar efeito
- Audit trail: tudo importante grava em audit_logs ou task_runs
- Best-effort em notificações: nunca quebra fluxo principal por falha de notif
