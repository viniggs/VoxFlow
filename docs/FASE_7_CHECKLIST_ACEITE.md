# VoxFlow 0.9.0 — Fase 7: empacotamento, versão e atualizador

Data: 2026-09-10

## A versão aparece no Windows

- [ ] No Explorer, clicar com o botão direito em
  `%LOCALAPPDATA%\Programs\VoxFlow\VoxFlow.exe` → **Propriedades** → **Detalhes** e
  confirmar que agora aparecem **Versão do arquivo 0.9.0**, **Nome do produto VoxFlow**
  e o fabricante. Antes vinha tudo em branco.
- [ ] Confirmar que o ícone do VoxFlow aparece no atalho e na janela.

## O atualizador

Em Ajustes → **Geral**:

- [ ] Confirmar que **Versão instalada** mostra `0.9.0`.
- [ ] Em **Origem de atualizações**, clicar em **Procurar…** e escolher
  `D:\Apps\WisprFlow\releases`.
- [ ] Clicar em **Verificar agora**: deve dizer que você já está na versão mais recente,
  e o botão **Instalar** deve ficar desabilitado.
- [ ] Deixar a origem **vazia** e verificar de novo: deve dizer que nenhuma origem está
  configurada — o app **não** procura atualização em lugar nenhum por conta própria.
- [ ] Apontar a origem para uma pasta que não existe e confirmar que ele diz isso, em vez
  de travar ou ficar calado.
- [ ] Confirmar que a janela **não congela** durante a verificação.

Quando sair uma versão nova, o teste completo é:

- [ ] **Verificar agora** encontra a versão nova e habilita **Instalar**.
- [ ] **Instalar** abre o instalador, que fecha o VoxFlow sozinho e sobe a versão nova.

## O critério de aceite da especificação

- [ ] **Numa máquina limpa** (a do teu amigo serve): instalar e conseguir ditar em menos
  de dois minutos. Lembrando que o Whisper baixa cerca de 1,6 GB na primeira transcrição,
  então o cronômetro vale a partir do modelo já baixado.
