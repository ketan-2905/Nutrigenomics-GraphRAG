from src.graph.queries import (
    find_paths_from_snp,
    find_foods_for_snp,
    find_nutrients_for_trait,
    find_graph_path,
    find_foods_for_trait,
)


def get_snp_context(snp_id: str) -> list[str]:
    evidence = []
    paths = find_paths_from_snp(snp_id)
    for p in paths[:10]:
        nodes = p.get("node_ids", [])
        rels = p.get("rel_types", [])
        if nodes:
            parts = []
            for i, node in enumerate(nodes):
                parts.append(node)
                if i < len(rels):
                    parts.append(f"-[{rels[i]}]->")
            evidence.append(" ".join(parts))
    return evidence


def get_trait_context(trait_name: str) -> list[str]:
    evidence = []
    nutrients = find_nutrients_for_trait(trait_name)
    for n in nutrients:
        evidence.append(f"Nutrient {n['nutrient']} is connected to {trait_name}")
    foods = find_foods_for_trait(trait_name)
    for f in foods:
        evidence.append(f"Food {f['food']} is connected to {trait_name}")
    return evidence


def get_path_context(source: str, target: str) -> list[str]:
    from src.graph.queries import find_graph_path
    paths = find_graph_path(source, target)
    evidence = []
    for p in paths:
        nodes = p.get("path_nodes", [])
        evidence.append(" -> ".join(nodes))
    return evidence
