# VoxFlow 0.2.0 — Checklist manual de aceite da Fase 1

Data: 2026-09-06

## Instalação e controle

- [ ] Instalar `VoxFlow-0.2.0-fase-1-setup.exe`.
- [ ] Confirmar que o processo VoxFlow permanece em segundo plano.
- [ ] Usar o atalho “Encerrar VoxFlow” do Menu Iniciar e confirmar que o processo termina.
- [ ] Abrir VoxFlow novamente pelo Menu Iniciar.

## Ditado no Bloco de Notas

- [ ] Abrir o Bloco de Notas e posicionar o cursor.
- [ ] Segurar `Ctrl + Numpad +`, dizer uma frase em português e soltar.
- [ ] Confirmar que o caractere `+` não aparece sozinho.
- [ ] Confirmar que a frase transcrita é colada no cursor.
- [ ] Confirmar que o clipboard textual anterior é restaurado.

## Ditado no Chrome

- [ ] Posicionar o cursor em uma caixa de texto no Chrome.
- [ ] Repetir o ditado com `Ctrl + Numpad +`.
- [ ] Confirmar que o texto aparece na caixa correta.

## Cancelamentos e latência

- [ ] Tocar rapidamente o atalho por menos de 400 ms e confirmar que nada é inserido.
- [ ] Segurar o atalho em silêncio e confirmar que nada é inserido.
- [ ] Abrir `%LOCALAPPDATA%\VoxFlow\logs\voxflow.log`.
- [ ] Encontrar `stt_ms`, `inject_ms` e `total_after_release_ms`.
- [ ] Confirmar latência após soltar inferior a 2,5 s após o modelo já estar aquecido.

Observação: a primeira execução carrega o modelo grande na GPU e pode demorar. O critério de latência vale para ditados após o aquecimento.

