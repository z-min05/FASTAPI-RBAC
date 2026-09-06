"""
加密现有 LLM 配置中的 api_key 明文数据（一次性迁移脚本）。

用法：python -m scripts.migrate_encrypt_api_keys
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.agent_llm import AgentLlm
from app.core.crypto_util import encrypt, decrypt


async def main():
    count = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AgentLlm))
        llms = list(result.scalars().all())
        for llm in llms:
            if not llm.api_key:
                continue
            # 尝试解密，如果成功说明已经是密文，跳过
            decrypted = decrypt(llm.api_key)
            if decrypted != llm.api_key:
                # 已经是密文（解密后和原文不同），跳过
                continue
            # 明文，需要加密
            llm.api_key = encrypt(llm.api_key)
            count += 1
        if count:
            await db.commit()
            print(f"已加密 {count} 条 api_key")
        else:
            print("没有需要加密的 api_key 数据")

    if count:
        print("请重启后端服务使新加密数据生效")


if __name__ == "__main__":
    asyncio.run(main())