"""
Thinning script for Delft3D FM .pli files.
Syncs polyline nodes with the thinned .bc indices.
"""
import re
from pathlib import Path

def linspace_indices(start: int, end: int, num: int) -> list[int]:
    """Calculates linear distributed indices (same logic as BC script)."""
    if num <= 1:
        return [start]
    step = (end - start) / (num - 1)
    return [round(start + step * i) for i in range(num)]

def main():
    # 1. Mesma lógica de seleção do script BC
    selected = set()
    selected.update(linspace_indices(1, 162, 10))
    selected.update(linspace_indices(162, 239, 10))
    selected.update(linspace_indices(239, 290, 10))
    selected.update(linspace_indices(290, 323, 5))
    
    sorted_indices = sorted(list(selected))
    print(f"Indices para manter: {sorted_indices}")

    input_path = Path(r"C:\Users\Unipa\Documents\StagnoneDT\model\dflowfm_v05\Stagnone_v05.pli")
    output_path = input_path.with_name("Stagnone_v05_thinned.pli")

    if not input_path.exists():
        print(f"Erro: Arquivo não encontrado em {input_path}")
        return

    lines = input_path.read_text(encoding='utf-8').splitlines()
    
    # Estrutura do PLI:
    # Linha 0: Nome da Polyline
    # Linha 1: N_pontos N_colunas
    # Linhas 2+: X Y Nome_do_Ponto
    
    polyline_name = lines[0]
    header_parts = lines[1].split()
    num_cols = header_parts[1] if len(header_parts) > 1 else "2"

    new_nodes = []
    for line in lines[2:]:
        if not line.strip():
            continue
        
        point_index += 1
        # Seleciona pela posição sequencial do ponto na lista original
        if point_index in selected:
            new_nodes.append(line)

    # 3. Escrita do novo arquivo com cabeçalho atualizado
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"{polyline_name}\n")
        f.write(f"    {len(new_nodes)}    {num_cols}\n")
        for node in new_nodes:
            f.write(f"{node}\n")
    
    print(f"\nSucesso!")
    print(f"Pontos originais: {lines[1].split()[0]}")
    print(f"Pontos reduzidos: {len(new_nodes)}")
    print(f"Salvo em: {output_path}")

if __name__ == "__main__":
    main()