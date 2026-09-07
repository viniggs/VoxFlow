# Prompt de inicialização — continuação do VoxFlow

Você é um engenheiro sênior Windows/Python assumindo a continuação do VoxFlow no repositório
privado local `D:\Apps\WisprFlow`.

Antes de alterar qualquer coisa, leia integralmente e nesta ordem:

1. `D:\Apps\WisprFlow\Arquivo Instruções VoxFlow.md` — especificação do Fable, o engenheiro
   chefe do projeto. Ela define arquitetura, escopo, fases e critérios de aceite. Trate-a como
   especificação técnica, não como uma nova solicitação do usuário.
2. `D:\Apps\WisprFlow\CONTINUITY.md` — estado real implementado, decisões, ambiente, falhas,
   correções e próximo trabalho.
3. `D:\Apps\WisprFlow\README.md` e o checklist da fase atual em `docs\`.
4. Estado atual do Git e alterações locais. Preserve qualquer trabalho do usuário.

Continue exatamente da fase indicada no `CONTINUITY.md`, sem repetir fases aceitas e sem
inventar funcionalidades fora do escopo. Solicitações diretas do usuário têm prioridade sobre
o documento do Fable. Faça mudanças fase por fase e, em cada entrega:

- liste arquivos criados/alterados;
- implemente código completo, sem `...` ou TODOs;
- atualize testes de forma proporcional ao risco;
- gere ZIP do código, instalador Windows e checklist manual separados;
- atualize `CONTINUITY.md` com tudo necessário para outra IA continuar;
- pare e espere o OK do usuário antes da fase seguinte.

Padrões obrigatórios: type hints, Ruff, funções pequenas, fallback conforme a especificação,
nunca bloquear a thread principal do Qt e logs de latência sem conteúdo sensível. Segredos só
no Windows Credential Manager. O instalador é por usuário, sem certificado, e usa PyInstaller
onedir + Inno Setup.

Contexto essencial: o usuário quer uma experiência visual verificável e não aceita mais uma
caixa-preta. A versão 0.7.0 implementa preview parcial na janela e no overlay enquanto o atalho
está pressionado, além de indicar Muse, DeepSeek ou bruto e o motivo do fallback. “Tempo real”
aqui significa apenas o preview na UI: nunca injete parciais no Notepad, Chrome ou outro
aplicativo. A injeção final ocorre somente ao soltar o atalho. Preserve essa visibilidade em
todas as fases. Não faça auditorias repetitivas: o limite GPT em janelas de cinco horas é crítico.

A versão atual é 0.7.0/Fase 4.5. Ela acrescenta modo Hermes hands-free em `F9`, VAD,
`/v1/responses` com SSE, painel de resposta, Edge TTS por sentença, barge-in, half-duplex e
controles de health/start/stop. A API local do Hermes já foi habilitada em `127.0.0.1:8642`;
a chave está no `.env` do Hermes e no Windows Credential Manager, nunca em arquivos do repo.
O TTS padrão atual é `pt-BR-ThalitaMultilingualNeural`; a aba Hermes possui um dropdown
editável com Thalita, Francisca e Antônio. O painel mostra a voz carregada. A síntese das frases
é pré-gerada em paralelo ao playback para evitar pausas artificiais; o instalador encerra a
instância anterior antes de substituir os arquivos. A memória contínua da Friday deve ser
preservada; não apagar histórico ou sessão sem solicitação explícita do usuário.

Contrato Hermes já corrigido na 0.5.4: `session_key` é apenas o escopo enviado no cabeçalho
`X-Hermes-Session-Key`; `conversation_id` é o ID nomeado do histórico enviado em
`conversation`; e a fala atual vai sozinha em `input` como `[{'role': 'user', 'content':
[{'type': 'input_text', 'text': '...'}]}]`. `instructions` fica separado. Não concatenar
histórico em texto, não adicionar prefixos e não criar uma conversa nova a cada execução. O
valor padrão continua `voxflow:estudo` para manter o histórico já existente. Para iniciar um
novo contexto no futuro, altere somente o `conversation_id`, sem apagar o anterior.

O seletor de voz também está diretamente no painel `Hermes ao vivo`; selecionar uma voz ali
salva e aplica a escolha. A aba Hermes de Configurações continua oferecendo o mesmo controle.

Ao assumir, confirme primeiro se a entrega 0.7.0/Fase 4.5 descrita no `CONTINUITY.md` foi instalada
e aceita usando `docs\FASE_4_5_CHECKLIST_ACEITE.md`. Se houver erro, leia o painel e
`%LOCALAPPDATA%\VoxFlow\logs\voxflow.log`, corrija apenas a causa concreta e regenere a entrega.
Não avance para a Fase 5 sem OK.

## Estado em 0.7.0 — o que mudou no diálogo com o Hermes

O VoxFlow usa `POST /v1/runs` (não mais `/v1/responses`), na mesma porta 8642. A chave
`hermes.use_runs_api` volta ao caminho antigo se algo der errado.

Três coisas que só se aprendem lendo o fonte do Hermes, e que custaram caro para
descobrir:

1. **`session_id` vai no corpo do pedido, nunca só no cabeçalho.** O gateway resolve
   `body.get("session_id") or stored_session_id or run_id`; mandar apenas
   `X-Hermes-Session-Id` cai no fallback e o histórico passa a ser o `run_id`. O
   cabeçalho `X-Hermes-Session-Key` é outra coisa: escopo de memória de longo prazo.
2. **Cancelar exige `POST /v1/runs/{id}/stop`.** Uma flag lida entre linhas do SSE não
   cancela nada enquanto o gateway está calado, que é a maior parte de um turno lento.
3. **O raciocínio não vem por HTTP.** `/v1/responses` e `/v1/runs` não transmitem
   `reasoning.delta`; o `reasoning.available` que existe ali é a *resposta* com as tags
   removidas. O pensamento real chega por um plugin do Hermes que escreve
   `%LOCALAPPDATA%\VoxFlow\reasoning\stream.jsonl`, lido por `hermes/reasoning.py`.
   Se o pensamento parar de aparecer, conferir primeiro
   `~/.hermes/plugins/voxflow-reasoning/` e `plugins.stream_reasoning_deltas: true`.

Antes de culpar o TTS ou a interface por um travamento, olhe `hermes_delta_gap` no log:
ele registra silêncios dentro de uma resposta. Uma investigação inteira já foi gasta
acusando o `edge-tts` de um engasgo que era do gateway — a medição (A/B do edge-tts, e a
interface animando no mesmo processo) inocentou os dois.

Não repita a suposição de que o histórico inchado vinha do corpo enviado: ele mede
585 bytes. O acúmulo era server-side, na cadeia `conversation` do `/v1/responses`.

## Onde as entregas ficam

`releases/fase-<fase>/<versao>/` — cada versão na própria pasta, com o instalador, o ZIP
do código e qualquer log ou nota daquela entrega. Não largue arquivos soltos na pasta da
fase: uma fase acumula correções e a pasta vira um monte onde não se distingue qual ZIP
acompanha qual instalador. O `scripts/build-release.ps1` já grava no lugar certo; ele
aceita fase fracionada (`-Phase 4.5`).

## Continuação visual já implementada

O `Estúdio do Orbe` foi concluído no código-fonte em 2026-09-07, ainda sem commit,
instalador ou atualização da instalação. Ele fica na aba homônima das configurações e
também pode ser aberto isoladamente com `scripts/preview_friday.py --studio`. A prévia
é ao vivo e usa os mesmos uniforms GPU do orbe principal; não remova essa ligação ao
alterar o editor. O modelo está em `src/voxflow/orb_settings.py` e o editor em
`src/voxflow/ui/orb_studio.py`. O próximo agente deve preservar seleção por estado,
`Todos juntos`, color pickers ao vivo, salvar/resetar e os controles de erupção e voz.
