from dataclasses import dataclass, field
from enum import IntEnum, unique
from os import path
import pickle
from typing import TypeAlias
from uuid import UUID, uuid4
import aiofiles
import networkx
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import vector
from config import config


@unique
class EntityType(IntEnum):
    """
    实体类型枚举

    - PERSON: 人物
    - PLACE: 地点
    - ITEM: 物品
    - ORGANIZATION: 组织
    """

    PERSON = 0  # pyright: ignore[reportCallIssue]
    PLACE = 1  # pyright: ignore[reportCallIssue]
    ITEM = 2  # pyright: ignore[reportCallIssue]
    ORGANIZATION = 3  # pyright: ignore[reportCallIssue]

    def __str__(self):
        match self:
            case EntityType.PERSON:
                return "人物"
            case EntityType.PLACE:
                return "地点"
            case EntityType.ITEM:
                return "物品"
            case EntityType.ORGANIZATION:
                return "组织"

    def __hash__(self):
        return hash(self.value)


@dataclass
class AttributeValue:
    """
    属性值

    - value: 属性值
    - timestamp_desc: 本属性值开始生效的时间描述
    """

    value: str
    timestamp_desc: str

    def __hash__(self):
        return hash((self.value, self.timestamp_desc))


@dataclass
class Entity:
    """
    实体

    - id: 实体唯一标识符
    - type: 实体类型
    - attributes: 实体属性列表
    """

    type: EntityType
    id: UUID = field(default_factory=lambda: uuid4())
    attributes: dict[str, list[AttributeValue]] = field(
        default_factory=dict[str, list[AttributeValue]]
    )

    def __hash__(self):
        return hash(self.id)


@dataclass
class Edge:
    """
    边

    - id: 边唯一标识符
    - attributes: 边属性列表
    """

    from_entity_id: UUID
    """
    起点实体的唯一标识符
    """

    to_entity_id: UUID
    """
    终点实体的唯一标识符
    """

    id: UUID = field(default_factory=lambda: uuid4())
    """
    边的唯一标识符
    """

    attributes: dict[str, list[AttributeValue]] = field(
        default_factory=dict[str, list[AttributeValue]]
    )
    """
    边的属性列表
    """

    def __hash__(self):
        return hash(self.id)


@dataclass
class SearchResultEntity:
    """
    搜索结果(实体)

    - id: 实体的唯一标识符
    - type: 实体类型
    - attributes: 属性信息
    - score: 相似度分数，数值越大表示越相似
    """

    id: str
    type: str
    attributes: dict[str, list[AttributeValue]]
    score: float


@dataclass
class SearchResultEdge:
    """
    搜索结果(边)

    - id: 边的唯一标识符
    - from_entity_id: 起点实体的唯一标识符
    - to_entity_id: 终点实体的唯一标识符
    - attributes: 属性信息
    - score: 相似度分数，数值越大表示越相似
    """

    id: str
    from_entity_id: str
    to_entity_id: str
    attributes: dict[str, list[AttributeValue]]
    score: float


SearchResult: TypeAlias = SearchResultEntity | SearchResultEdge
"""搜索结果，可能是实体也可能是边"""


class World:
    def __init__(self, persistent_path: str | None = None):
        """
        创建一个空白的世界记忆

        - persistent_path: 如果提供，则使用该目录进行持久化存储。

        注意，在它的任何异步方法之前，必须先调用 initialize() 进行异步资源的初始化
        """

        if persistent_path is None:
            self.client = AsyncQdrantClient(location=":memory:")
            self.graph_location = None
        else:
            qdrant_location = path.abspath(persistent_path) + "/qdrant"
            self.client = AsyncQdrantClient(path=qdrant_location)
            self.graph_location = path.abspath(persistent_path) + "/graph.pkl"

        if self.graph_location is None:
            self.graph: networkx.MultiDiGraph[UUID] = networkx.MultiDiGraph()
        else:
            try:
                self.graph: networkx.MultiDiGraph[UUID] = load_graph_from_file(
                    file_path=self.graph_location
                )
            except GraphLoadError:
                self.graph = networkx.MultiDiGraph()

    async def initialize(self):
        """
        初始化一些异步资源，必须在创建之后尽早调用
        """
        await self.client.recreate_collection(
            collection_name="world",
            vectors_config=VectorParams(
                size=config.vector_dimension, distance=Distance.COSINE
            ),
        )

    async def add_entity(self, entity: Entity):
        """
        添加实体

        - entity: 实体对象

        如果实体已存在则抛出异常
        """
        if entity.id in self.graph:
            raise ValueError(f"Entity with id {entity.id} already exists.")
        self.graph.add_node(entity.id, entity=entity)
        entity_attributes_str = "\n".join(
            f"{key}：{', '.join(f'{av.value} ({av.timestamp_desc})' for av in values)}"
            for key, values in entity.attributes.items()
        )
        entity_str = f"""实体属性：
{entity_attributes_str}
"""
        entity_vector = await vector.generate_vector(entity_str)
        if entity_vector is None:
            raise ValueError("Failed to generate vector for entity.")
        attributes_payload = {
            key: [
                {"value": av.value, "timestamp_desc": av.timestamp_desc}
                for av in values
            ]
            for key, values in entity.attributes.items()
        }
        point = PointStruct(
            id=str(entity.id),
            vector=entity_vector,
            payload={
                "id": str(entity.id),
                "type": str(entity.type),
                "attributes": attributes_payload,
            },
        )
        await self.client.upsert(
            collection_name="world",
            points=[point],
        )

    async def add_edge(self, from_entity_id: UUID, to_entity_id: UUID, edge: Edge):
        """
        添加边

        - from_entity_id: 起点实体的唯一标识符
        - to_entity_id: 终点实体的唯一标识符
        - edge: 边对象

        如果边已存在，或者起点或终点实体不存在则抛出异常
        """
        if from_entity_id not in self.graph or to_entity_id not in self.graph:
            raise ValueError("Both entities must exist in the graph.")
        if edge.id in self.graph:
            raise ValueError(f"Edge with id {edge.id} already exists.")
        self.graph.add_edge(from_entity_id, to_entity_id, key=edge.id, edge=edge)
        edge_attributes_str = "\n".join(
            f"{key}：{', '.join(f'{av.value} ({av.timestamp_desc})' for av in values)}"
            for key, values in edge.attributes.items()
        )
        edge_str = f"""边属性：
{edge_attributes_str}
"""
        edge_vector = await vector.generate_vector(edge_str)
        if edge_vector is None:
            raise ValueError("Failed to generate vector for edge.")
        attributes_payload = {
            key: [
                {"value": av.value, "timestamp_desc": av.timestamp_desc}
                for av in values
            ]
            for key, values in edge.attributes.items()
        }

        point = PointStruct(
            id=str(edge.id),
            vector=edge_vector,
            payload={
                "id": str(edge.id),
                "type": "边",
                "from_entity_id": str(from_entity_id),
                "to_entity_id": str(to_entity_id),
                "attributes": attributes_payload,
            },
        )
        await self.client.upsert(
            collection_name="world",
            points=[point],
        )

    async def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """
        搜索与查询最相关的实体和边

        - query: 查询字符串
        - limit: 返回结果数量上限

        返回搜索结果列表，包含实体和边
        """
        query_vector = await vector.generate_vector(query)
        if query_vector is None:
            raise ValueError("Failed to generate vector for query.")
        search_result = await self.client.search(
            collection_name="world",
            limit=limit,
            query_vector=query_vector,
            with_payload=True,
        )
        # 解析搜索结果
        results: list[SearchResult] = []
        for point in search_result:
            payload = point.payload
            if payload is None:
                raise ValueError("Search result payload is None. Borken data?")
            if payload.get("type") == "边":
                result = SearchResultEdge(
                    id=payload["id"],
                    from_entity_id=payload["from_entity_id"],
                    to_entity_id=payload["to_entity_id"],
                    attributes={
                        key: [
                            AttributeValue(
                                value=av["value"], timestamp_desc=av["timestamp_desc"]
                            )
                            for av in values
                        ]
                        for key, values in payload.get("attributes", {}).items()
                    },
                    score=point.score,
                )
            else:
                result = SearchResultEntity(
                    id=payload["id"],
                    type=payload["type"],
                    attributes={
                        key: [
                            AttributeValue(
                                value=av["value"], timestamp_desc=av["timestamp_desc"]
                            )
                            for av in values
                        ]
                        for key, values in payload.get("attributes", {}).items()
                    },
                    score=point.score,
                )
            results.append(result)
        return results

    def get_entity(self, entity_id: UUID) -> Entity | None:
        """
        根据实体ID获取实体

        - entity_id: 实体的唯一标识符

        如果实体不存在则返回None
        """
        node_data = self.graph.nodes.get(entity_id)
        if node_data is None:
            return None
        return node_data.get("entity")

    def get_edge(self, edge_id: UUID) -> Edge | None:
        """
        根据边ID获取边

        - edge_id: 边的唯一标识符

        如果边不存在则返回None
        """
        for _, _, key, edge_data in self.graph.edges(data=True, keys=True):
            if key == edge_id:
                return edge_data.get("edge")
        return None

    async def delete_entity(self, entity_id: UUID) -> bool:
        """
        删除实体及其相关的所有边

        - entity_id: 实体的唯一标识符

        返回True表示删除成功，False表示实体不存在
        """
        if entity_id not in self.graph:
            return False
        self.graph.remove_node(entity_id)
        # 删除向量数据库中的该实体
        await self.client.delete(
            collection_name="world", points_selector=[str(entity_id)], wait=True
        )
        # 删除所有from_entity_id等于指定实体ID的边
        await self.client.delete(
            collection_name="world",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="from_entity_id",
                            match=models.MatchValue(value=str(entity_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

        # 删除所有to_entity_id等于指定实体ID的边
        await self.client.delete(
            collection_name="world",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="to_entity_id",
                            match=models.MatchValue(value=str(entity_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )
        return True

    async def replace_entity(self, entity: Entity) -> bool:
        """
        替换实体

        - entity: 实体对象

        返回True表示替换成功，False表示实体不存在
        """
        if entity.id not in self.graph:
            return False
        self.graph.nodes[entity.id]["entity"] = entity
        entity_attributes_str = "\n".join(
            f"{key}：{', '.join(f'{av.value} ({av.timestamp_desc})' for av in values)}"
            for key, values in entity.attributes.items()
        )
        entity_str = f"""实体属性：
{entity_attributes_str}
"""
        entity_vector = await vector.generate_vector(entity_str)
        if entity_vector is None:
            raise ValueError("Failed to generate vector for entity.")
        attributes_payload = {
            key: [
                {"value": av.value, "timestamp_desc": av.timestamp_desc}
                for av in values
            ]
            for key, values in entity.attributes.items()
        }
        point = PointStruct(
            id=str(entity.id),
            vector=entity_vector,
            payload={
                "id": str(entity.id),
                "type": str(entity.type),
                "attributes": attributes_payload,
            },
        )
        await self.client.upsert(
            collection_name="world",
            points=[point],
        )
        return True

    async def replace_edge(self, edge: Edge) -> bool:
        """
        替换边

        - edge: 边对象

        返回True表示替换成功，False表示边不存在
        """
        for u, v, key in list(self.graph.edges(keys=True)):
            if key == edge.id:
                self.graph[u][v][key]["edge"] = edge
                edge_attributes_str = "\n".join(
                    f"{key}：{', '.join(f'{av.value} ({av.timestamp_desc})' for av in values)}"
                    for key, values in edge.attributes.items()
                )
                edge_str = f"""边属性：
{edge_attributes_str}
"""
                edge_vector = await vector.generate_vector(edge_str)
                if edge_vector is None:
                    raise ValueError("Failed to generate vector for edge.")
                attributes_payload = {
                    key: [
                        {"value": av.value, "timestamp_desc": av.timestamp_desc}
                        for av in values
                    ]
                    for key, values in edge.attributes.items()
                }
                point = PointStruct(
                    id=str(edge.id),
                    vector=edge_vector,
                    payload={
                        "id": str(edge.id),
                        "type": "边",
                        "from_entity_id": str(edge.from_entity_id),
                        "to_entity_id": str(edge.to_entity_id),
                        "attributes": attributes_payload,
                    },
                )
                await self.client.upsert(
                    collection_name="world",
                    points=[point],
                )
                return True
        return False

    async def delete_edge(self, edge_id: UUID) -> bool:
        """
        删除边

        - edge_id: 边的唯一标识符

        返回True表示删除成功，False表示边不存在
        """
        for u, v, key in list(self.graph.edges(keys=True)):
            if key == edge_id:
                self.graph.remove_edge(u, v, key=edge_id)
                # 删除向量数据库中的该边
                await self.client.delete(
                    collection_name="world",
                    points_selector=[str(edge_id)],
                    wait=True,
                )

                return True
        return False

    def get_related_edges(
        self, entity_id: UUID
    ) -> list[tuple[Entity, Edge, Entity]] | None:
        """
        获取与指定实体相关的所有边，并自动去重。

        包括以该实体为起点或终点的边。
        返回(开始实体, 边, 结束实体)列表。

        如果实体不存在则返回None。
        """
        if entity_id not in self.graph:
            return None

        # 使用 set 来自动处理重复的边（例如自环）
        found_edges: set[tuple[Entity, Edge, Entity]] = set()

        # 获取所有出边 (entity -> neighbor)
        for u, v, _, edge_data in self.graph.out_edges(entity_id, data=True, keys=True):
            edge = edge_data.get("edge")
            if edge:
                # 这里的 u, v 分别是起点和终点的 ID
                start_entity = self.get_entity(u)
                end_entity = self.get_entity(v)
                if start_entity and end_entity:
                    found_edges.add((start_entity, edge, end_entity))

        # 获取所有入边 (predecessor -> entity)
        for u, v, _, edge_data in self.graph.in_edges(entity_id, data=True, keys=True):
            edge = edge_data.get("edge")
            if edge:
                start_entity = self.get_entity(u)
                end_entity = self.get_entity(v)
                if start_entity and end_entity:
                    found_edges.add((start_entity, edge, end_entity))

        return list(found_edges)

    def get_edges_between(
        self, from_entity_id: UUID, to_entity_id: UUID
    ) -> list[Edge] | None:
        """
        获取两个实体之间的所有边

        - from_entity_id: 起点实体的唯一标识符
        - to_entity_id: 终点实体的唯一标识符

        如果任一实体不存在则返回None
        """
        if from_entity_id not in self.graph or to_entity_id not in self.graph:
            return None
        edges: list[Edge] = []
        edges_raw = self.graph.get_edge_data(from_entity_id, to_entity_id, default={})
        # 转回list[Edge]
        for edge_data in edges_raw.values():
            edge = edge_data.get("edge")
            if edge:
                edges.append(edge)
        return edges

    def __str__(self):
        """
        为 World 对象提供一个易于阅读的字符串表示形式，用于调试。
        """
        num_entities = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()

        lines = [
            "--- World State ---",
            f"  Entities: {num_entities}",
            f"  Edges:    {num_edges}",
            "-------------------",
        ]

        if num_entities == 0:
            return "\n".join(lines)

        # 1. 遍历并展示实体摘要
        lines.append("Entities:")
        id_to_name_map: dict[UUID, str] = {}
        for entity_id, data in self.graph.nodes(data=True):
            entity = data.get("entity")
            if not entity:
                continue

            # 尝试从属性中获取一个可读的名称，否则回退到ID
            name_values = entity.attributes.get("名字")
            if name_values:
                # 使用最新的名字
                name = name_values[-1].value
                entity_repr = f"{name} ({entity.type})"
                id_to_name_map[entity_id] = name
            else:
                entity_repr = f"{entity.type} (ID: {str(entity_id)[:8]})"
                id_to_name_map[entity_id] = f"ID:{str(entity_id)[:8]}"

            lines.append(f"  - {entity_repr:<40} | ID: {entity_id}")

        # 2. 遍历并展示边摘要
        if num_edges > 0:
            lines.append("\nEdges:")
            for u, v, data in self.graph.edges(data=True):
                edge = data.get("edge")
                if not edge:
                    continue

                u_name = id_to_name_map.get(u, f"ID:{str(u)[:8]}")
                v_name = id_to_name_map.get(v, f"ID:{str(v)[:8]}")

                # 尝试为边找到一个有意义的标签
                edge_label = f"ID:{str(edge.id)[:8]}"  # 默认标签
                relation_values = edge.attributes.get("关系")
                if relation_values:
                    edge_label = relation_values[-1].value
                else:
                    type_values = edge.attributes.get("类型")
                    if type_values:
                        edge_label = type_values[-1].value

                lines.append(f"  - {u_name} --[{edge_label}]--> {v_name}")

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """
        生成当前世界状态的 Mermaid 流程图代码。
        """
        if self.graph.number_of_nodes() == 0:
            return "flowchart LR\n    subgraph World\n        direction LR\n        empty[世界是空的]\n    end"

        lines = ["flowchart LR"]  # LR = Left to Right, 从左到右布局

        uuid_to_node_id: dict[UUID, str] = {}

        # --- 1. 定义所有节点 (实体) ---
        lines.append("\n    %% Entities")
        for entity_id, data in self.graph.nodes(data=True):
            entity = data.get("entity")
            if not entity:
                continue

            # Mermaid的节点ID不能有-，我们进行替换
            node_id = f"E_{str(entity_id).replace('-', '')}"
            uuid_to_node_id[entity_id] = node_id

            # 获取节点显示名
            name_values = entity.attributes.get("名字")
            if name_values:
                # Mermaid标签内的引号需要转义
                label_text = name_values[-1].value.replace('"', "#quot;")
            else:
                label_text = f"ID:{str(entity_id)[:8]}"

            # 生成节点定义，格式：NodeID["显示文本(类型)"]
            lines.append(f'    {node_id}["{label_text} ({entity.type})"]')

        # --- 2. 定义所有链接 (边) ---
        lines.append("\n    %% Edges")
        for u, v, data in self.graph.edges(data=True):
            edge = data.get("edge")
            if not edge:
                continue

            start_node = uuid_to_node_id.get(u)
            end_node = uuid_to_node_id.get(v)

            if not start_node or not end_node:
                continue

            # 获取边的标签
            edge_label = ""
            relation_values = edge.attributes.get("关系")
            if relation_values:
                edge_label = relation_values[-1].value.replace('"', "#quot;")

            # 生成链接定义，格式：StartNode -- "标签" --> EndNode
            lines.append(f'    {start_node} -- "{edge_label}" --> {end_node}')

        return "\n".join(lines)

    async def sync_to_disk(self):
        """
        将世界状态同步到持久化存储（如果有的话）
        """
        if self.graph_location is not None:
            data = pickle.dumps(self.graph)
            async with aiofiles.open(self.graph_location, "wb") as f:
                await f.write(data)


class GraphLoadError(Exception):
    """从 Pickle 文件加载图时发生错误的基类"""

    pass


def load_graph_from_file(file_path: str) -> "nx.MultiDiGraph[UUID]":  # type: ignore  # noqa: F821
    """
    从指定 pickle 文件加载图数据。
    如果失败，则抛出 GraphLoadError 异常。

    - file_path: 图数据文件路径

    返回加载的图对象。
    """
    try:
        with open(file_path, "rb") as f:
            graph_obj = pickle.load(f)

        # 验证加载的对象是不是我们期望的 MultiDiGraph 类型
        if not isinstance(graph_obj, networkx.MultiDiGraph):
            raise GraphLoadError(
                f"文件 '{file_path}' 中包含的不是一个有效的 MultiDiGraph 对象，而是 {type(graph_obj)} 类型。"
            )

        return graph_obj  # pyright: ignore[reportUnknownVariableType]

    except FileNotFoundError as e:
        raise GraphLoadError(f"找不到图文件 '{file_path}'。") from e
    except pickle.UnpicklingError as e:
        # 文件损坏或格式不兼容
        raise GraphLoadError(f"图文件 '{file_path}' 已损坏或格式不兼容。") from e
    except IOError as e:
        # 其他可能的 IO 错误，如权限问题
        raise GraphLoadError(f"读取图文件 '{file_path}' 时发生 IO 错误。") from e
