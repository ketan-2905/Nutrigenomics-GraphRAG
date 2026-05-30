from src.db.neo4j_client import Neo4jClient


def find_paths_from_snp(snp_id: str):
    db = Neo4jClient()
    query = """
    MATCH path = (s:SNP {id:$snp_id})-[:RELATED*1..5]-(n)
    RETURN [node in nodes(path) | coalesce(node.id, '')] AS node_ids,
           [rel in relationships(path) | rel.type] AS rel_types
    LIMIT 25
    """
    result = db.run(query, {"snp_id": snp_id})
    db.close()
    return result


def find_foods_for_snp(snp_id: str):
    db = Neo4jClient()
    query = """
    MATCH path = (s:SNP {id:$snp_id})-[:RELATED*1..6]-(f:Food)
    RETURN f.id AS food,
           [node in nodes(path) | coalesce(node.id, '')] AS path_nodes
    LIMIT 20
    """
    result = db.run(query, {"snp_id": snp_id})
    db.close()
    return result


def find_nutrients_for_trait(trait_name: str):
    db = Neo4jClient()
    query = """
    MATCH path = (n:Nutrient)-[:RELATED*1..3]-(t:Trait {id:$trait_name})
    RETURN n.id AS nutrient,
           [node in nodes(path) | coalesce(node.id, '')] AS path_nodes
    LIMIT 20
    """
    result = db.run(query, {"trait_name": trait_name})
    db.close()
    return result


def find_graph_path(source_id: str, target_id: str):
    db = Neo4jClient()
    query = """
    MATCH path = shortestPath((a {id:$source})-[:RELATED*1..8]-(b {id:$target}))
    RETURN [node in nodes(path) | coalesce(node.id, '')] AS path_nodes,
           [rel in relationships(path) | rel.type] AS rel_types
    LIMIT 5
    """
    result = db.run(query, {"source": source_id, "target": target_id})
    db.close()
    return result


def find_foods_for_trait(trait_name: str):
    db = Neo4jClient()
    query = """
    MATCH path = (f:Food)-[:RELATED*1..4]-(t:Trait {id:$trait_name})
    RETURN f.id AS food,
           [node in nodes(path) | coalesce(node.id, '')] AS path_nodes
    LIMIT 20
    """
    result = db.run(query, {"trait_name": trait_name})
    db.close()
    return result


def get_graph_summary():
    db = Neo4jClient()
    result = db.run("MATCH ()-[r:RELATED]->() RETURN count(r) AS edge_count")
    node_result = db.run("MATCH (n) RETURN count(n) AS node_count")
    db.close()
    return {
        "edge_count": result[0]["edge_count"] if result else 0,
        "node_count": node_result[0]["node_count"] if node_result else 0,
    }
