# Notificações seguras

O despacho externo começa desativado. Para habilitá-lo, o ambiente deve definir a URL HTTPS, o segredo HMAC e uma allowlist explícita de hosts. O sistema não envia CNIS, CPF, nome do cliente, documentos ou conteúdo do dossiê.

Cada entrega inclui um `Idempotency-Key`, timestamp e assinatura HMAC. O receptor deve validar a assinatura, descartar replays e buscar detalhes somente por um canal autenticado próprio.
