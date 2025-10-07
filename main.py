import asyncio
from project_instant import ProjectInstant
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent import world_setup_graph
import agent
import project_instant


async def main():
    # instant = await project_instant.load_from_directory("datas/834e34c6-fd52-4532-a4f7-0a93f5952dc6") # 换为特定的路径以加载已有项目用于测试
    instant = ProjectInstant("test")
    await instant.initialize()

    # 初始化状态
    state: agent.State = {
        "messages": [],
        "world": instant.world,
        "chapter_infos": instant.chapter_infos,
        "outline": instant.outline,
    }

    # 构建图
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            # 将新用户输入添加到当前 state 中
            current_messages = state.get("messages", [])
            current_messages.append(HumanMessage(content=user_input))
            state["messages"] = current_messages

            final_state_snapshot = None
            async for event in world_setup_graph.astream(  # type: ignore
                state, config={"recursion_limit": 114514}
            ):  # type: ignore
                for node_name, value_update in event.items():
                    print(f"--- [节点: {node_name}] ---")

                    if "messages" in value_update:
                        new_messages = value_update["messages"]
                        if new_messages:
                            latest_message = new_messages[-1]
                            if isinstance(latest_message, AIMessage):
                                if latest_message.tool_calls:
                                    tool_name = latest_message.tool_calls[0]["name"]
                                    print(
                                        f"🤖 Assistant (思考): 准备调用工具 `{tool_name}`..."
                                    )
                                elif latest_message.content:
                                    print(f"🤖 Assistant: {latest_message.content}")
                            elif isinstance(latest_message, ToolMessage):
                                print(
                                    f"🛠️ Tool Result (`{latest_message.name}`): {latest_message.content}"
                                )

                # 保存每个步骤结束后的完整状态快照
                final_state_snapshot = event

            print("\n--- [流程结束] ---\n")

            if final_state_snapshot:
                last_node_name = list(final_state_snapshot.keys())[-1]
                state.update(
                    final_state_snapshot[last_node_name]
                )  # 合并 state 与最后一个节点的输出

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

    await project_instant.save_to_directory(instant)


if __name__ == "__main__":
    asyncio.run(main())
