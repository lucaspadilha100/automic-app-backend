# Correções finais de alinhamento ao prompt inicial

## Implementado nesta rodada

- Portal do cliente final com schemas seguros para não expor `internal_notes`.
- Correção de `AppointmentReview.customer_account_id` para usar o cliente autenticado.
- Regra real de no-show para pacotes usando `consume_package_session_on_no_show`.
- Compatibilidade de `package_sessions` com `status` (`reserved`, `used`, `cancelled`) mantendo `action` legado.
- Compatibilidade de `customer_packages` com `purchase_price`, `created_by_user_id`, status `fully_used` e `payment_status=partially_paid`, mantendo campos legados.
- `unit_id` opcional em `professionals`, `resources` e `business_hours`.
- `tenant_id` em `customer_tag_links`.
- Campos `note` e `visibility` em `customer_notes`, mantendo `content` e `is_internal` legados.
- Campos `old_status`, `new_status`, `changed_by_user_id` e `changed_by_customer_id` em `appointment_status_history`, mantendo `from_status/to_status` legados.
- Tabela `theme_presets` e seed dos presets iniciais.
- Seed dos planos atualizado para `Start`, `Pro` e `Premium`.
- Rate limiting simples em memória para login interno e login do cliente final.
- Migration incremental `0003_prompt_alignment_fixes.py`.
- `validate_backend.py` atualizado para checar as novas estruturas.
- README atualizado com as correções finais.

## Validação feita neste ambiente

- `python -m compileall -q app scripts alembic`: OK.

## Validação pendente no ambiente do projeto

Como este ambiente não possui as dependências instaladas (`sqlalchemy`, FastAPI etc.), rode localmente ou no Claude/Codex:

```bash
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
python -m pytest tests/ -v
python scripts/validate_backend.py
```

## Rodada final de fechamento do prompt

Correções adicionais aplicadas:

- Corrigido `POST /api/v1/appointment-holds` para não referenciar `current_customer` inexistente em rota administrativa.
- `AppointmentHoldCreate` agora aceita `customer_account_id` opcional para vínculo administrativo seguro.
- Criação de tenant pelo Console Master agora cria também `TenantPaymentSettings`, unidade principal e assinatura padrão `Start` quando existir.
- Criação de unidade permite a primeira/unidade principal mesmo sem feature `multi_unit`; unidades extras continuam exigindo feature e limite de plano.
- `CustomerTagLink` agora grava `tenant_id` e filtra por `tenant_id` ao vincular/desvincular tags.
- `CustomerNoteCreate` aceita `note`/`visibility` e mantém compatibilidade com `content`/`is_internal`.
- `media_service.py`, `invite_service.py`, `customer_timeline_service.py` e `unit_service.py` receberam lógica útil de negócio em vez de placeholders vazios.
- GETs faltantes do Console Master adicionados para plano, settings e tema.
- Migration incremental `0004_final_prompt_closure.py` criada para backfill/fechamento visual de schema.
- Testes smoke atualizados para cobrir os fechamentos finais.
