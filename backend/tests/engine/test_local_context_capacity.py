"""Managed launch arguments must leave a usable context for every client slot."""

from types import SimpleNamespace

import pytest

from store_emulator.application import local_vlm, providers
from store_emulator.application.hardware import GPUInfo, downgrade, recommend
from store_emulator.application.local_vlm import LocalVLMManager
from tests.engine.test_local_vlm import _hw


@pytest.mark.parametrize('vendor,vram,arch', [
    ('nvidia', 6, 'x64'), ('nvidia', 12, 'x64'), ('nvidia', 24, 'arm64'),
    ('apple', 16, 'arm64'), ('amd', 8, 'x64'), ('intel', 4, 'x64'), ('cpu', 0, 'x64'),
])
def test_launched_context_and_advertised_slots_agree_without_growing_the_kv_pool(tmp_path, monkeypatch, vendor, vram, arch):
    hardware = _hw(os='macos' if vendor == 'apple' else 'linux', arch=arch,
                   gpus=[] if vendor == 'cpu' else [GPUInfo(vendor=vendor, name='offline GPU', vram_gb=vram)])
    plan = recommend(hardware)
    manager = LocalVLMManager(tmp_path, hardware=lambda: hardware)
    manager._set(plan=plan)
    commands = []
    configured = []
    process = SimpleNamespace(poll=lambda: None)

    def popen(command, **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(local_vlm.subprocess, 'Popen', popen)
    monkeypatch.setattr(local_vlm, '_end_with_this_process', lambda proc: None)
    monkeypatch.setattr(local_vlm, '_port_free', lambda port: True)
    monkeypatch.setattr(local_vlm, 'manager', lambda: manager)
    monkeypatch.setattr(manager, '_answers', lambda port: True)
    monkeypatch.setattr(providers, 'use_local_server', configured.append)
    manager._serve(tmp_path / 'llama-server', tmp_path / 'model.gguf', tmp_path / 'projector.gguf', plan)

    command = commands[0]
    total_context = int(command[command.index('-c') + 1])
    slots = int(command[command.index('-np') + 1])
    # llama.cpp's default non-unified KV divides -c by -np. The former 4K slots
    # rejected catalog inputs measured at 6,909 tokens, before producing a reply.
    assert total_context // slots >= 8192
    assert total_context == (16384 if vendor == 'nvidia' else 8192)
    assert slots == (2 if vendor == 'nvidia' else 1)
    assert manager.status().slots == slots
    assert providers.resolve_model('llamacpp:local', settings={}).max_parallel == slots
    assert configured == ['http://127.0.0.1:8081/v1']


@pytest.mark.parametrize('vendor', ['nvidia', 'apple', 'amd'])
def test_gpu_fallback_keeps_a_full_context_for_the_cpu_request(vendor):
    hardware = _hw(arch='arm64' if vendor == 'apple' else 'x64',
                   gpus=[GPUInfo(vendor=vendor, name='offline GPU', vram_gb=12)])
    cpu = downgrade(recommend(hardware), hardware)
    assert cpu.backend == 'cpu' and cpu.context == 8192 and cpu.parallel == 1
