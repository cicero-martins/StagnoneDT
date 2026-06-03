"""
Thinning script for Delft3D FM .bc files.
Reduces boundary condition density based on specific range requirements.
"""
import re
from pathlib import Path

def linspace_indices(start: int, end: int, num: int) -> list[int]:
    """Calculates linear distributed indices including endpoints."""
    if num <= 1:
        return [start]
    step = (end - start) / (num - 1)
    return [round(start + step * i) for i in range(num)]

def main():
    # 1. Definição dos índices desejados com base no seu pedido
    # 0001 a 0162 (10 pontos), 162 a 239 (10), 239 a 290 (10), 290 a 323 (5)
    selected = set()
    selected.update(linspace_indices(1, 162, 10))
    selected.update(linspace_indices(162, 239, 10))
    selected.update(linspace_indices(239, 290, 10))
    selected.update(linspace_indices(290, 323, 5))
    
    sorted_indices = sorted(list(selected))
    print(f"Indices selecionados ({len(sorted_indices)}): {sorted_indices}")

    base_dir = Path(r"C:\Users\Unipa\Documents\StagnoneDT\model\dflowfm_v05")
    filenames = [
        "waterlevelbnd_CMEMS_Stagnone_v05.bc",
        "salinitybnd_CMEMS_Stagnone_v05.bc",
        "temperaturebnd_CMEMS_Stagnone_v05.bc"
    ]

    for fname in filenames:
        input_path = base_dir / fname
        output_path = input_path.with_name(fname.replace(".bc", "_thinned.bc"))

        if not input_path.exists():
            print(f"Aviso: Arquivo não encontrado: {fname}")
            continue

        print(f"Processando {fname}...")
        content = input_path.read_text(encoding='utf-8')

        # 2. Split do arquivo preservando o cabeçalho
        blocks = re.split(r'(?=\[(?:Boundary|Forcing)\])', content)
        header = blocks[0] if not blocks[0].strip().startswith('[') else ""
        data_blocks = blocks if not header else blocks[1:]

        new_content = [header]
        count = 0

        for block in data_blocks:
            # Procura pelo número que vem após o ÚLTIMO sublinhado no nome/location
            match = re.search(r'(?:location|name)\s*=\s*.*_(\d+)', block, re.IGNORECASE)
            if match:
                idx = int(match.group(1))
                if idx in selected:
                    count += 1
                    new_id_str = f"{count:04d}"
                    # O USO DE \g<1> É CRITICIAL: evita que \10001 seja lido como octal
                    updated_block = re.sub(
                        r'((?:location|name)\s*=\s*.*_)(\d+)', 
                        rf'\g<1>{new_id_str}', 
                        block, 
                        flags=re.IGNORECASE
                    )
                    new_content.append(updated_block)
            else:
                if block.strip():
                    new_content.append(block)

        # 3. Escrita do novo arquivo
        output_path.write_text("".join(new_content), encoding='utf-8')
        print(f"  Sucesso: {len(data_blocks)} -> {count} pontos. Salvo em {output_path.name}")

    print("\nAVISO: Lembre-se que o arquivo .pli (polyline) correspondente")
    print("também deve ser reduzido para os mesmos indices para manter a consistência.")

if __name__ == "__main__":
    main()