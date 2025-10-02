import asyncio
from enum import Enum
from typing import Annotated
import uuid
from langchain_core.tools import tool, BaseTool  # type: ignore
from langgraph.prebuilt import InjectedState

from pydantic import BaseModel, Field


from agent_tools.outline_tools import get_outline_tool
from world import AttributeValue, Edge, Entity, EntityType, SearchResultEntity, World


class AttributeValueModel(BaseModel):
    """
    属性值输入
    """

    value: str = Field(description="属性的具体值。")
    """
    属性的具体内容
    """
    timestamp_desc: str = Field(
        description="描述该属性值生效时间点的自然语言，例如 '童年时', '在2024年', '当他拿起圣剑后'。"
    )
    """
    属性的生效时间点描述
    """


class EntityTypeEnum(str, Enum):
    """
    基于字符串的实体类型枚举
    """

    PERSON = "人物"
    PLACE = "地点"
    ITEM = "物品"
    ORGANIZATION = "组织"


@tool
def add_entity_tool(
    type: EntityTypeEnum,
    attributes: dict[str, list[AttributeValueModel]],
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    在世界记忆图谱中添加一个新实体。

    - type: 实体的类型，必须是 '人物', '地点', '物品', '组织' 之一。
    - attributes: 描述实体属性的字典。
      - 键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“年龄”。
      - 值: 一个列表，包含该属性类别的具体描述。
      - 注意，直接使用属性类别作为键，直接使用属性值列表作为值。不要使用"key"/"value"或者"属性类别"等多余键值。
    """
    try:
        final_entity_type: EntityType
        match type:
            case EntityTypeEnum.PERSON:
                final_entity_type = EntityType.PERSON
            case EntityTypeEnum.PLACE:
                final_entity_type = EntityType.PLACE
            case EntityTypeEnum.ITEM:
                final_entity_type = EntityType.ITEM
            case EntityTypeEnum.ORGANIZATION:
                final_entity_type = EntityType.ORGANIZATION
        entity_attributes = {
            key: [
                AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                for av in values
            ]
            for key, values in attributes.items()
        }
        new_entity = Entity(type=final_entity_type, attributes=entity_attributes)
        asyncio.run(world.add_entity(new_entity))
        return f"成功添加实体，ID: {new_entity.id}"
    except Exception as e:
        return f"添加实体时出错: {str(e)}"


@tool
def add_edge_tool(
    from_entity_id: str,
    to_entity_id: str,
    attributes: dict[str, list[AttributeValueModel]],
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    在世界记忆图谱中添加一条新边。

    - from_entity_id: 起始实体的 ID。
    - to_entity_id: 目标实体的 ID。
    - attributes: 描述边属性的字典。
      - 键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“年龄”。
      - 值: 一个列表，包含该属性类别的具体描述。
      - 注意，直接使用属性类别作为键，直接使用属性值列表作为值。不要使用"key"/"value"或者"属性类别"等多余键值。
    """
    try:
        from_entity_uuid = uuid.UUID(from_entity_id)
        to_entity_uuid = uuid.UUID(to_entity_id)
        edge_attributes = {
            key: [
                AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                for av in values
            ]
            for key, values in attributes.items()
        }
        new_edge = Edge(
            attributes=edge_attributes,
            from_entity_id=from_entity_uuid,
            to_entity_id=to_entity_uuid,
        )
        asyncio.run(
            world.add_edge(
                from_entity_id=from_entity_uuid,
                to_entity_id=to_entity_uuid,
                edge=new_edge,
            )
        )
        return f"成功添加边，ID: {new_edge.id}"
    except Exception as e:
        return f"添加边时出错: {str(e)}"


class SearchResultEntityOutput(BaseModel):
    """
    图搜索结果（实体）
    """

    id: str = Field(description="实体的唯一标识符（UUID）。")
    """
    实体的唯一标识符
    """

    type: EntityTypeEnum = Field(
        description="实体的类型，必须是 '人物', '地点', '物品', '组织' 之一。"
    )
    """
    实体的类型
    """

    score: float = Field(
        description="实体与搜索查询的相关性评分，数值越高表示相关性越强。"
    )
    """
    实体的相关性评分
    """


class SearchResultEdgeOutput(BaseModel):
    """
    图搜索结果（边）
    """

    id: str = Field(description="边的唯一标识符（UUID）。")
    """
    边的唯一标识符
    """

    from_entity_id: str = Field(description="起始实体的唯一标识符（UUID）。")
    """
    起始实体的唯一标识符
    """

    to_entity_id: str = Field(description="目标实体的唯一标识符（UUID）。")
    """
    目标实体的唯一标识符
    """

    score: float = Field(
        description="边与搜索查询的相关性评分，数值越高表示相关性越强。"
    )
    """
    边的相关性评分
    """


@tool
def search_graph_tool(
    query: str,
    limit: int,
    world: Annotated[World, InjectedState("world")],
) -> list[SearchResultEntityOutput | SearchResultEdgeOutput] | str:
    """
    在世界记忆图谱中搜索相关的实体或者边

    注意搜索结果不包括实体或边的属性详情，只包含 ID、类型和相关性评分，如果需要获取详情，请使用 `get_entity_tool` 或 `get_edge_tool`。

    - query: 搜索的自然语言描述
    - limit: 返回结果的最大数量
    """
    try:
        results = asyncio.run(world.search(query, limit=limit))

        if len(results) == 0:
            return "未找到任何相关的实体或边。"

        output_results: list[SearchResultEntityOutput | SearchResultEdgeOutput] = []
        for item in results:
            if isinstance(item, SearchResultEntity):
                final_entity_type: EntityTypeEnum
                match item.type:
                    case "人物":
                        final_entity_type = EntityTypeEnum.PERSON
                    case "地点":
                        final_entity_type = EntityTypeEnum.PLACE
                    case "物品":
                        final_entity_type = EntityTypeEnum.ITEM
                    case "组织":
                        final_entity_type = EntityTypeEnum.ORGANIZATION
                    case _:
                        raise ValueError(
                            f"未知的实体类型: {item.type}"
                        )  # 除非图数据损坏，这不可能发生，因此直接抛出异常
                output_results.append(
                    SearchResultEntityOutput(
                        id=str(item.id),
                        type=final_entity_type,
                        score=item.score,
                    )
                )
            elif isinstance(item, Edge):
                output_results.append(
                    SearchResultEdgeOutput(
                        id=str(item.id),
                        from_entity_id=str(item.from_entity_id),
                        to_entity_id=str(item.to_entity_id),
                        score=item.score,
                    )
                )
        return output_results
    except Exception as e:
        return f"搜索世界记忆图谱时出错: {str(e)}"


class EntityOutput(BaseModel):
    """
    实体信息输出
    """

    id: str = Field(description="实体的唯一标识符（UUID）。")
    """
    实体的唯一标识符
    """

    type: EntityTypeEnum = Field(
        description="实体的类型，必须是 '人物', '地点', '物品', '组织' 之一。"
    )
    """
    实体的类型
    """

    attributes: dict[str, list[AttributeValueModel]] = Field(
        description="""描述实体属性的字典。
      字典的键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“年龄”。
      字典的值: 一个列表，包含该属性类别的具体描述。
"""
    )
    """
    实体的属性字典
    """


@tool
def get_entity_tool(
    entity_id: str,
    world: Annotated[World, InjectedState("world")],
) -> EntityOutput | str:
    """
    根据实体 ID 获取实体的详细信息

    - entity_id: 实体的唯一标识符（UUID）
    """
    try:
        entity_uuid = uuid.UUID(entity_id)
        entity = world.get_entity(entity_uuid)
        if entity is None:
            return f"未找到 ID 为 {entity_id} 的实体。"
        final_entity_type: EntityTypeEnum
        match entity.type:
            case EntityType.PERSON:
                final_entity_type = EntityTypeEnum.PERSON
            case EntityType.PLACE:
                final_entity_type = EntityTypeEnum.PLACE
            case EntityType.ITEM:
                final_entity_type = EntityTypeEnum.ITEM
            case EntityType.ORGANIZATION:
                final_entity_type = EntityTypeEnum.ORGANIZATION
        attribute_models = {
            key: [
                AttributeValueModel(value=av.value, timestamp_desc=av.timestamp_desc)
                for av in values
            ]
            for key, values in entity.attributes.items()
        }
        return EntityOutput(
            id=str(entity.id),
            type=final_entity_type,
            attributes=attribute_models,
        )
    except Exception as e:
        return f"获取实体信息时出错: {str(e)}"


class EdgeOutput(BaseModel):
    """
    边信息输出
    """

    id: str = Field(description="边的唯一标识符（UUID）。")
    """
    边的唯一标识符
    """

    from_entity_id: str = Field(description="起始实体的唯一标识符（UUID）。")
    """
    起始实体的唯一标识符
    """

    to_entity_id: str = Field(description="目标实体的唯一标识符（UUID）。")
    """
    目标实体的唯一标识符
    """

    attributes: dict[str, list[AttributeValueModel]] = Field(
        description="""描述边属性的字典。
      字典的键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“关系”。
      字典的值: 一个列表，包含该属性类别的具体描述。
"""
    )
    """
    边的属性字典
    """


@tool
def get_edge_tool(
    edge_id: str,
    world: Annotated[World, InjectedState("world")],
) -> EdgeOutput | str:
    """
    根据边 ID 获取边的详细信息

    - edge_id: 边的唯一标识符（UUID）
    """
    try:
        edge_uuid = uuid.UUID(edge_id)
        edge = world.get_edge(edge_uuid)
        if edge is None:
            return f"未找到 ID 为 {edge_id} 的边。"
        attribute_models = {
            key: [
                AttributeValueModel(value=av.value, timestamp_desc=av.timestamp_desc)
                for av in values
            ]
            for key, values in edge.attributes.items()
        }
        return EdgeOutput(
            id=str(edge.id),
            from_entity_id=str(edge.from_entity_id),
            to_entity_id=str(edge.to_entity_id),
            attributes=attribute_models,
        )
    except Exception as e:
        return f"获取边信息时出错: {str(e)}"


class RelatedEdgeOutput(BaseModel):
    """
    相关边信息输出
    """

    start_entity: str = Field(description="起始实体的唯一标识符（UUID）。")
    """
    起始实体的唯一标识符
    """

    edge: str = Field(description="边的唯一标识符（UUID）。")
    """
    边的唯一标识符
    """

    end_entity: str = Field(description="目标实体的唯一标识符（UUID）。")
    """
    目标实体的唯一标识符
    """


@tool
def get_related_edges_tool(
    entity_id: str,
    world: Annotated[World, InjectedState("world")],
) -> list[RelatedEdgeOutput] | str:
    """
    根据实体 ID 获取与该实体相关的所有边

    - entity_id: 实体的唯一标识符（UUID）
    """
    try:
        entity_uuid = uuid.UUID(entity_id)
        edges = world.get_related_edges(entity_uuid)

        if edges is None:
            return f"ID 为 {entity_id} 的实体不存在"

        if len(edges) == 0:
            return f"ID 为 {entity_id} 的实体没有任何相关的边。"

        output_edges: list[RelatedEdgeOutput] = []
        for start, edge, end in edges:
            start_entity_id = str(start.id)
            end_entity_id = str(end.id)
            edge_id = str(edge.id)
            output_edges.append(
                RelatedEdgeOutput(
                    start_entity=start_entity_id, edge=edge_id, end_entity=end_entity_id
                )
            )
        return output_edges
    except Exception as e:
        return f"获取相关边信息时出错: {str(e)}"


class EdgeBetweenEntitiesOutput(BaseModel):
    """
    实体间边信息输出
    """

    id: str = Field(description="边的唯一标识符（UUID）。")
    """
    边的唯一标识符
    """

    from_entity_id: str = Field(description="起始实体的唯一标识符（UUID）。")
    """
    起始实体的唯一标识符
    """

    to_entity_id: str = Field(description="目标实体的唯一标识符（UUID）。")
    """
    目标实体的唯一标识符
    """


@tool
def get_edges_between_entities_tool(
    from_entity_id: str,
    to_entity_id: str,
    world: Annotated[World, InjectedState("world")],
) -> list[EdgeBetweenEntitiesOutput] | str:
    """
    根据起始实体 ID 和目标实体 ID 获取它们之间的所有边

    - from_entity_id: 起始实体的唯一标识符（UUID）
    - to_entity_id: 目标实体的唯一标识符（UUID）
    """
    try:
        from_entity_uuid = uuid.UUID(from_entity_id)
        to_entity_uuid = uuid.UUID(to_entity_id)
        edges = world.get_edges_between(from_entity_uuid, to_entity_uuid)

        if edges is None:
            return f"ID 为 {from_entity_id} 或 {to_entity_id} 的实体不存在"

        if len(edges) == 0:
            return f"ID 为 {from_entity_id} 和 {to_entity_id} 的实体之间没有任何边。"

        output_edges: list[EdgeBetweenEntitiesOutput] = []
        for edge in edges:
            edge_output = EdgeBetweenEntitiesOutput(
                id=str(edge.id),
                from_entity_id=str(edge.from_entity_id),
                to_entity_id=str(edge.to_entity_id),
            )
            output_edges.append(edge_output)
        return output_edges
    except Exception as e:
        return f"获取实体间边信息时出错: {str(e)}"


@tool
def delete_entity_tool(
    entity_id: str,
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    根据实体 ID 删除实体，注意这也会删除与该实体相关的所有边

    - entity_id: 实体的唯一标识符（UUID）
    """
    try:
        entity_uuid = uuid.UUID(entity_id)
        success = asyncio.run(world.delete_entity(entity_uuid))
        if success:
            return f"成功删除 ID 为 {entity_id} 的实体。"
        else:
            return f"未找到 ID 为 {entity_id} 的实体。"
    except Exception as e:
        return f"删除实体时出错: {str(e)}"


@tool
def delete_edge_tool(
    edge_id: str,
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    根据边 ID 删除边，注意这不会删除与该边相关的实体，即使这可能使得实体孤立

    - edge_id: 边的唯一标识符（UUID）
    """
    try:
        edge_uuid = uuid.UUID(edge_id)
        success = asyncio.run(world.delete_edge(edge_uuid))
        if success:
            return f"成功删除 ID 为 {edge_id} 的边。"
        else:
            return f"未找到 ID 为 {edge_id} 的边。"
    except Exception as e:
        return f"删除边时出错: {str(e)}"


@tool
def append_entity_attributes_tool(
    entity_id: str,
    new_attributes: dict[str, AttributeValueModel],
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    新增属性到实体中，如果属性类别已存在，则新增属性值到该类别的列表中。注意，这不会覆盖实体当前的属性列表（如有），而是新增到现有属性列表中。

    强烈建议在调用此工具前，先使用 `get_entity_tool` 获取当前实体的信息。如果有相当接近的属性类别已经存在，必须使用该类别以避免重复并保持时间顺序。只有明确发现没有切合的属性类别时，才新增一个新的类别。

    - entity_id: 实体的唯一标识符（UUID）
    - new_attributes: 描述实体新属性的字典。
      - 键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“年龄”。
      - 值: 对该属性类别新增的具体描述。
      - 注意，直接使用属性类别作为键，直接使用属性值列表作为值。不要使用"key"/"value"或者"属性类别"等多余键值。
    """
    try:
        entity_uuid = uuid.UUID(entity_id)
        entity = world.get_entity(entity_uuid)
        if entity is None:
            return f"未找到 ID 为 {entity_id} 的实体。"
        for key, av in new_attributes.items():
            if key in entity.attributes:
                entity.attributes[key].append(
                    AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                )
            else:
                entity.attributes[key] = [
                    AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                ]
        asyncio.run(world.replace_entity(entity))
        return f"成功更新 ID 为 {entity_id} 的实体属性。"
    except Exception as e:
        return f"更新实体属性时出错: {str(e)}"


@tool
def replace_entity_attributes_tool(
    entity_id: str,
    new_attributes: dict[str, list[AttributeValueModel]],
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    替换实体的所有属性为新的属性

    注意，这会完全覆盖实体当前的属性，而不是新增到现有属性中。

    建议在使用此工具之前先考虑是否能使用 `append_entity_attributes_tool` 来新增属性以完成目标，只有明确需要覆盖时才使用此工具。
    强烈建议在调用此工具前，先使用 `get_entity_tool` 获取当前实体的信息。

    - entity_id: 实体的唯一标识符（UUID）
    - new_attributes: 描述实体新属性的字典。
      - 键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“年龄”。
      - 值: 一个列表，包含该属性类别的具体描述。
      - 注意，直接使用属性类别作为键，直接使用属性值列表作为值。不要使用"key"/"value"或者"属性类别"等多余键值。
    """
    try:
        entity_uuid = uuid.UUID(entity_id)
        entity = world.get_entity(entity_uuid)
        if entity is None:
            return f"未找到 ID 为 {entity_id} 的实体。"
        updated_attributes = {
            key: [
                AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                for av in values
            ]
            for key, values in new_attributes.items()
        }
        entity.attributes = updated_attributes
        asyncio.run(world.replace_entity(entity))
        return f"成功更新 ID 为 {entity_id} 的实体属性。"
    except Exception as e:
        return f"更新实体属性时出错: {str(e)}"


@tool
def append_edge_attributes_tool(
    edge_id: str,
    new_attributes: dict[str, AttributeValueModel],
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    新增属性到边中，如果属性类别已存在，则新增属性值到该类别的列表中。注意，这不会覆盖边当前的属性列表（如有），而是新增到现有属性列表中。

    强烈建议在调用此工具前，先使用 `get_edge_tool` 获取当前边的信息。如果有相当接近的属性类别已经存在，必须使用该类别以避免重复并保持时间顺序。只有明确发现没有切合的属性类别时，才新增一个新的类别。

    - edge_id: 边的唯一标识符（UUID）
    - new_attributes: 描述边新属性的字典。
      - 键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“关系”。
      - 值: 对该属性类别新增的具体描述。
      - 注意，直接使用属性类别作为键，直接使用属性值列表作为值。不要使用"key"/"value"或者"属性类别"等多余键值。
    """
    try:
        edge_uuid = uuid.UUID(edge_id)
        edge = world.get_edge(edge_uuid)
        if edge is None:
            return f"未找到 ID 为 {edge_id} 的边。"
        for key, av in new_attributes.items():
            if key in edge.attributes:
                edge.attributes[key].append(
                    AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                )
            else:
                edge.attributes[key] = [
                    AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                ]
        asyncio.run(world.replace_edge(edge))
        return f"成功更新 ID 为 {edge_id} 的边属性。"
    except Exception as e:
        return f"更新边属性时出错: {str(e)}"


@tool
def replace_edge_attributes_tool(
    edge_id: str,
    new_attributes: dict[str, list[AttributeValueModel]],
    world: Annotated[World, InjectedState("world")],
) -> str:
    """
    替换边的所有属性为新的属性

    注意，这会完全覆盖边当前的属性，而不是新增到现有属性中。

    建议在使用此工具之前先考虑是否能使用 `append_edge_attributes_tool` 来新增属性以完成目标，只有明确需要覆盖时才使用此工具。
    强烈建议在调用此工具前，先使用 `get_edge_tool` 获取当前边的信息。

    - edge_id: 边的唯一标识符（UUID）
    - new_attributes: 描述边新属性的字典。
      - 键: 属性的类别，必须是一个字符串，代表这个属性客观分类的描述，如“关系”。
      - 值: 一个列表，包含该属性类别的具体描述。
      - 注意，直接使用属性类别作为键，直接使用属性值列表作为值。不要使用"key"/"value"或者"属性类别"等多余键值。
    """
    try:
        edge_uuid = uuid.UUID(edge_id)
        edge = world.get_edge(edge_uuid)
        if edge is None:
            return f"未找到 ID 为 {edge_id} 的边。"
        updated_attributes = {
            key: [
                AttributeValue(value=av.value, timestamp_desc=av.timestamp_desc)
                for av in values
            ]
            for key, values in new_attributes.items()
        }
        edge.attributes = updated_attributes
        asyncio.run(world.replace_edge(edge))  # replace触发向量库更新
        return f"成功更新 ID 为 {edge_id} 的边属性。"
    except Exception as e:
        return f"更新边属性时出错: {str(e)}"


full_tools: list[BaseTool] = [
    get_outline_tool,
    add_entity_tool,
    add_edge_tool,
    search_graph_tool,
    get_entity_tool,
    get_edge_tool,
    get_related_edges_tool,
    get_edges_between_entities_tool,
    delete_entity_tool,
    delete_edge_tool,
    append_entity_attributes_tool,
    replace_entity_attributes_tool,
    append_edge_attributes_tool,
    replace_edge_attributes_tool,
]
"""
完整的世界记忆图谱工具列表，包括读取、添加、删除和更新实体及边的功能。
"""

read_only_tools: list[BaseTool] = [
    get_outline_tool,
    search_graph_tool,
    get_entity_tool,
    get_edge_tool,
    get_related_edges_tool,
    get_edges_between_entities_tool,
]
"""
只读的世界记忆图谱工具列表，仅包括读取实体和边的功能，不包括任何修改图谱的操作。
"""
