# Bindings (C++ / Otimizações)

Espaço reservado para códigos C++/CUDA e bindings via pybind11 que aceleram operações pesadas (máscara de nuvens, reprojeção, estatísticas).

Estrutura sugerida:
- `cpp/libcore/`: kernels em C++ (cloud mask, reprojection...).
- `bindings/pybind_core.cpp`: expõe funções para Python (`core.bindings.fast`).
- Uso opcional, com fallback para implementações puras em NumPy quando o módulo não estiver disponível.
