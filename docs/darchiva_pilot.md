# Piloto dArchiva × PrevIA

## Objetivo

Validar se o dArchiva melhora a ingestão, OCR, qualidade e busca de documentos
do PrevIA sem substituir o CRM, a triagem ou as regras dos benefícios.

## Limites do piloto

- Executar em ambiente isolado e local.
- Usar somente cópias anonimizadas ou autorizadas para teste.
- Não transmitir documentos de clientes ao dArchiva, a um modelo VLM ou a
  qualquer serviço externo durante a avaliação.
- O PrevIA permanece como sistema de registro de leads, jornadas e regras dos
  benefícios; dArchiva é candidato a serviço documental.

## Conjunto de avaliação

Criar um `manifest.json` com documentos dos 11 fluxos. Para cada arquivo,
registrar campos verdadeiros já conferidos por humano.

```json
{
  "documents": [
    {
      "id": "cnis-nativo-001",
      "document_code": "CNIS",
      "path": "C:/piloto-anonimizado/cnis-001.pdf",
      "critical_fields": ["cpf", "nit", "competencias", "vinculos"],
      "expected": {"cpf": "000.000.000-00", "nit": "00000000000"}
    }
  ]
}
```

Cobertura mínima: CNIS, CTPS, PPP/LTCAT, CAT, laudo/atestado, CadÚnico,
comprovantes de renda, certidões de óbito/nascimento, carta de concessão,
processo administrativo e documento de reclusão.

## Linha de base atual

Execute sem qualquer serviço externo:

```powershell
py darchiva_pilot.py manifest.json --output baseline_local.json
```

O relatório mede o acerto por campo e guarda somente metadados e notas técnicas;
ele não grava o texto completo do documento.

## Critérios para integrar

1. Melhorar a acurácia dos campos críticos em relação à linha de base.
2. Preservar referência de página/trecho para toda extração usada em decisão.
3. Nenhum campo crítico pode ser automaticamente aceito sem validação de formato
   e regra previdenciária.
4. O processamento deve ser assíncrono, sem bloquear o CRM.
5. Documentos originais, permissões e auditoria devem permanecer sob controle
   do escritório.

## Próxima dependência

O computador atual não possui Docker. Antes de subir o dArchiva, instalar Docker
Desktop e executar o piloto em uma máquina/ambiente separado do PrevIA ativo.
