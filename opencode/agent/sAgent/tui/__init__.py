"""sAgent 表现层(TUI, Textual 实现)。

只通过两样东西接触 core: Agent 的 run_turn/reset API + 事件契约(core.events)。
界面更新一律经 post_message 投递回 UI 线程,worker 线程不直接操作 widget。
"""
