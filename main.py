import asyncio
from world import AttributeValue, Edge, Entity, EntityType, World


async def main():
    world = World()
    await world.initialize()

    # 实体：克莱恩·莫雷蒂
    klein = Entity(
        type=EntityType.PERSON,
        attributes={
            "名字": [
                AttributeValue(value="周明瑞", timestamp_desc="“穿越”前"),
                AttributeValue(
                    value="克莱恩·莫雷蒂", timestamp_desc="“穿越”后，占据了原主的身体"
                ),
            ],
            "序列": [
                AttributeValue(
                    value="序列9：占卜家", timestamp_desc="成为非凡者后的初始序列"
                ),
            ],
        },
    )

    # 实体：邓恩·史密斯
    dunn_smith = Entity(
        type=EntityType.PERSON,
        attributes={
            "名字": [AttributeValue(value="邓恩·史密斯", timestamp_desc="故事开始时")],
            "职位": [
                AttributeValue(
                    value="值夜者小队队长", timestamp_desc="廷根市值夜者负责人"
                )
            ],
            "特征": [
                AttributeValue(
                    value="记性很差，发际线高", timestamp_desc="非凡特性带来的副作用"
                )
            ],
        },
    )

    # 实体：值夜者组织
    nighthawks = Entity(
        type=EntityType.ORGANIZATION,
        attributes={
            "名字": [
                AttributeValue(
                    value="值夜者", timestamp_desc="黑夜女神教会的武力机构之一"
                )
            ]
        },
    )

    # 实体：圣赛琳娜教堂
    st_selena_cathedral = Entity(
        type=EntityType.PLACE,
        attributes={
            "名字": [
                AttributeValue(
                    value="圣赛琳娜教堂", timestamp_desc="黑夜女神教会位于廷根市的教堂"
                )
            ]
        },
    )

    # 实体：安提哥努斯家族笔记
    antigonus_notebook = Entity(
        type=EntityType.ITEM,
        attributes={
            "名字": [
                AttributeValue(value="安提哥努斯家族笔记", timestamp_desc="故事开始时")
            ],
            "描述": [
                AttributeValue(
                    value="一本危险的非凡物品，记载了占卜家途径的信息",
                    timestamp_desc="来源神秘",
                )
            ],
        },
    )

    # --- 2. 将实体添加到世界中 ---
    await world.add_entity(klein)
    await world.add_entity(dunn_smith)
    await world.add_entity(nighthawks)
    await world.add_entity(st_selena_cathedral)
    await world.add_entity(antigonus_notebook)

    # --- 3. 创建并添加实体间的关系（边） ---

    # 关系：克莱恩加入值夜者
    klein_joins_nighthawks = Edge(
        attributes={
            "关系": [AttributeValue(value="成员", timestamp_desc="通过考验后正式加入")],
        }
    )
    await world.add_edge(klein.id, nighthawks.id, klein_joins_nighthawks)

    # 关系：邓恩是值夜者的队长
    dunn_is_captain = Edge(
        attributes={
            "关系": [
                AttributeValue(value="领导", timestamp_desc="作为队长领导廷根市值夜者")
            ],
        }
    )
    await world.add_edge(dunn_smith.id, nighthawks.id, dunn_is_captain)

    # 关系：值夜者位于教堂地下
    nighthawks_in_cathedral = Edge(
        attributes={
            "关系": [
                AttributeValue(
                    value="位于",
                    timestamp_desc="其总部位于教堂的地下区域，如查尼斯门后",
                )
            ],
        }
    )
    await world.add_edge(nighthawks.id, st_selena_cathedral.id, nighthawks_in_cathedral)

    # 关系：克莱恩获得安提哥努斯笔记
    klein_obtains_notebook = Edge(
        attributes={
            "关系": [AttributeValue(value="获得", timestamp_desc="在一次任务中查获")],
            "事件": [
                AttributeValue(value="查尼斯门事件", timestamp_desc="相关联的关键事件")
            ],
        }
    )
    await world.add_edge(klein.id, antigonus_notebook.id, klein_obtains_notebook)

    # --- 4. 打印最终的世界状态 ---
    print("--- 复杂世界构建完成 ---")
    print(world)
    print("```mermaid")
    print(world.to_mermaid())
    print("```")

    # 测试查询
    print("\n--- 测试查询 ---")
    print("查询克莱恩的所有关系：")
    klein_edges = world.get_related_edges(klein.id)
    if klein_edges is not None:
        for edge in klein_edges:
            print(edge)


if __name__ == "__main__":
    asyncio.run(main())
