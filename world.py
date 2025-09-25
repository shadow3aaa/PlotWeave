from dataclasses import dataclass, field
from enum import Enum, unique
from uuid import UUID, uuid4
import networkx


@unique
class EntityType(Enum):
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

    id: UUID = field(default_factory=lambda: uuid4())
    attributes: dict[str, list[AttributeValue]] = field(
        default_factory=dict[str, list[AttributeValue]]
    )

    def __hash__(self):
        return hash(self.id)


class World:
    def __init__(self):
        self.graph: networkx.MultiDiGraph[UUID] = networkx.MultiDiGraph()

    def add_entity(self, entity: Entity):
        """
        添加实体

        如果实体已存在则抛出异常
        """
        if entity.id in self.graph:
            raise ValueError(f"Entity with id {entity.id} already exists.")
        self.graph.add_node(entity.id, entity=entity)

    def add_edge(self, from_entity_id: UUID, to_entity_id: UUID, edge: Edge):
        """
        添加边

        如果边已存在，或者起点或终点实体不存在则抛出异常
        """
        if from_entity_id not in self.graph or to_entity_id not in self.graph:
            raise ValueError("Both entities must exist in the graph.")
        if edge.id in self.graph:
            raise ValueError(f"Edge with id {edge.id} already exists.")
        self.graph.add_edge(from_entity_id, to_entity_id, key=edge.id, edge=edge)
