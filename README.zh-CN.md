# AltCoin 项目

![Language](https://img.shields.io/badge/language-Python-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

[English](./README.md) | [中文](./README.zh-CN.md)

## 关于项目

AltCoin 是一个为了学习目的、从零开始构建的基础区块链协议实现。本项目的首要目标并非创造一种新的金融资产，而是作为一个透明的、可动手实践的全栈平台，帮助开发者深度理解区块链技术的第一性原理。

这个项目覆盖了一个区块链系统的完整生命周期，从核心的数据结构和共识机制，到包含节点、浏览器和钱包的应用生态。

### 项目哲学

> 我们坚信，理解一个复杂系统的最佳方式是亲手构建它。

本项目旨在弥合抽象的区块链理论与具体的工程实践之间的巨大鸿沟。

## 核心特性

* **共识机制**: 基于双重SHA256 (SHA256d) 的工作量证明 (PoW)。
* **数据模型**: 未花费的交易输出 (UTXO) 模型。
* **数据存储**: 紧凑的二进制格式用于区块的磁盘存储。
* **网络**: 一个简化的P2P网络层，并对外提供JSON-RPC API。
* **密码学**: 基于 `SECP256k1` 曲线的ECDSA数字签名算法。
* **地址**: 采用以太坊风格的 `0x` 前缀十六进制地址，并支持EIP-55校验和。

## 项目结构

```
altcoin-core/
├── doc/                # 文档 (白皮书, API规范等)
├── src/                # 源代码
│   ├── core/           # 核心数据结构 (区块, 交易)
│   ├── consensus/      # 共识逻辑 (PoW)
│   ├── network/        # P2P网络通信
│   ├── api/            # JSON-RPC API服务
│   ├── storage/        # 磁盘存储管理
│   ├── utils/          # 密码学和序列化工具
│   └── main.py         # 运行节点的主入口
├── test/               # 单元测试和集成测试
└── requirements.txt    # 项目依赖
```

## 开始使用

请遵循以下步骤来启动并运行你的本地节点。

### 环境要求

* Python 3.8+

### 安装与设置

1.  **克隆仓库:**
    ```sh
    git clone [https://github.com/](https://github.com/)[你的用户名]/altcoin-core.git
    cd altcoin-core
    ```
2.  **创建并激活虚拟环境:**
    ```sh
    python -m venv venv
    source venv/bin/activate  # Windows系统请使用 `venv\Scripts\activate`
    ```
3.  **安装依赖:**
    ```sh
    pip install -r requirements.txt
    ```

### 运行节点

1.  **运行测试以确保一切正常:**
    ```sh
    python -m unittest discover
    ```
2.  **启动你的节点:**
    ```sh
    python src/main.py
    ```

## 项目路线图

AltCoin的开发计划分为三个主要阶段：

1.  **第一阶段：核心节点**
    * 实现一个稳定、功能完备的节点客户端，具备P2P网络、挖矿、交易和区块验证能力。
2.  **第二阶段：区块浏览器**
    * 开发一个基于Web的区块浏览器，为链上状态提供一个透明的实时数据窗口。
3.  **第三阶段：钱包**
    * 创建一个用户友好的钱包应用（桌面/Web版），用于管理密钥、查询余额和创建交易。

## 许可证

本项目采用 MIT 许可证。详情请参阅 `LICENSE` 文件。