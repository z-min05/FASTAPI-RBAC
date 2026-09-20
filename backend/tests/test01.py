import re
import os
import asyncio
import edge_tts
import textwrap


# ============================================
#  文本清洗：去掉 Markdown 符号
# ============================================

def clean_for_tts(text):
    """清洗 AI 输出中的 Markdown 和特殊符号"""

    # 先去掉公共缩进（解决多行字符串的缩进问题）
    text = textwrap.dedent(text)

    # 代码块
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 行内代码
    text = re.sub(r'`([^`]*)`', r'\1', text)
    # 标题 #（行首可有空白）
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    # 加粗/斜体
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    # 链接 [text](url)
    text = re.sub(r'$$([^$$]+)\]$$[^$$]+\)', r'\1', text)
    # 图片 ![alt](url)
    text = re.sub(r'!$$([^$$]*)\]$$[^$$]+\)', r'\1', text)
    # 表格线
    text = re.sub(r'\|[-:]+\|', '', text)
    text = re.sub(r'\|', ' ', text)
    # 引用 >（行首可有空白）
    text = re.sub(r'^\s*>\s?', '', text, flags=re.MULTILINE)
    # 列表符号（行首可有空白）
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 分隔线 --- *** ___（行首可有空白）
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # 装饰符号
    text = re.sub(r'[→▶★☆•◆●■□►➤➜]', '', text)
    # 多余空行 → 单个换行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 每行首尾空白
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    # 再清一次多余空行
    text = re.sub(r'\n{2,}', '\n', text)

    return text.strip()


# ============================================
#  TTS 转换
# ============================================

async def tts_convert(text, output_path="output.mp3", voice="zh-CN-XiaoxiaoNeural", rate="+20%"):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)
    return output_path


def text_to_speech(
    text,
    output_path="output.mp3",
    voice="zh-CN-XiaoxiaoNeural",
    rate="+0%",
    clean=True
):
    """
    主函数：清洗文本 + 生成语音

    参数:
        text        : 输入文本（可带 Markdown）
        output_path : 输出 mp3 路径
        voice       : 声音模型
        rate        : 语速  "-20%" 慢 / "+30%" 快
        clean       : 是否自动清洗 Markdown
    """
    print(f"原文长度: {len(text)} 字符")

    if clean:
        text = clean_for_tts(text)
        print(f"清洗后: {len(text)} 字符")
        print("--- 清洗结果预览 ---")
        print(text[:500])
        print("---" + "-" * 20)

    if not text:
        print("错误：清洗后文本为空")
        return None

    print(f"声音: {voice}")
    print("正在生成语音...")

    result = asyncio.run(tts_convert(text, output_path, voice, rate))

    file_size = os.path.getsize(output_path) / 1024
    print(f"完成: {output_path} ({file_size:.1f} KB)")
    return result


def file_to_speech(input_file, output_file=None, voice="zh-CN-XiaoxiaoNeural"):
    """从 txt/md 文件读取并转语音"""

    if not os.path.exists(input_file):
        print(f"错误：文件不存在 - {input_file}")
        return None

    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    if output_file is None:
        base = os.path.splitext(input_file)[0]
        output_file = f"{base}.mp3"

    return text_to_speech(text, output_file, voice=voice)


# ============================================
#  使用示例
# ============================================

if __name__ == "__main__":

    # ---- 示例 1：中文 ----
    ai_output = """
    哈哈，叫我贾维斯也行！😎 不过我先把刚才的任务结果给你 ——

## 📊 test_platform 服务状态检查报告

**✅ 总体状态：运行正常**

| 检查项 | 结果 |
|--------|------|
| **系统服务** | `test_platform.service` 已启用，**active (running)**，已稳定运行约 22 小时 |
| **进程** | Gunicorn 主进程 (PID 4016341) + 工作进程 (PID 4016343) 均正常运行 |
| **端口监听** | `127.0.0.1:8887` 正常监听中 |
| **健康检查** | HTTP **200**，返回 `{"status":"ok"}`，响应仅 **5.8ms**，非常快 |
| **内存占用** | 约 251 MB，处于正常水平 |
| **数据库连接** | PostgreSQL 有多个 test_platform 连接，均处于 idle 正常状态 |
| **错误日志** | 最近 30 分钟**无报错/异常**（日志里出现的 "error" 字样是正常的 agent 消息复位记录，非服务故障） |

**结论**：test_platform 后端服务健康，接口响应迅速，无异常。一切正常，Sir！🫡

---

另外，我就是你的私人 AI 管家——**贾维斯**随时待命！有什么需要我去做的？比如查看日志、检查代码、部署调试，尽管吩咐～
    """

    text_to_speech(
        text=ai_output,
        output_path="python_intro.mp3",
        voice="zh-CN-XiaoyiNeural"
    )

    # # ---- 示例 2：英文 ----
    # english = """
    # # How to Learn Python

    # Python is one of the **most popular** programming languages.
    # It is used in web development, data science, and AI.

    # Start learning today!
    # """

    # text_to_speech(
    #     text=english,
    #     output_path="english.mp3",
    #     voice="en-US-JennyNeural"
    # )