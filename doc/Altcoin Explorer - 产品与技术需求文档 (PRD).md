# Altcoin Explorer - 产品与技术需求文档 (PRD)

## 1. 产品愿景与核心原则

**产品名称**: Altcoin Scan (scan.altcoin.host)

**产品愿景**: 为 Altcoin 生态的用户、开发者和爱好者，提供一个界面精致、数据精确、响应迅速的区块链浏览器，使其成为洞察链上活动、追踪交易、验证数据的首选入口。

**核心设计原则**:
- **数据驱动**: 核心功能是展示数据。界面设计必须以清晰、准确地呈现数据为第一优先级。
- **精致简约**: 遵循现代Web设计美学，使用 Tailwind CSS 构建一个干净、有呼吸感、信息层级分明的界面。避免不必要的设计元素干扰。
- **响应式体验**: 确保在桌面、平板和移动设备上都有一流的浏览体验。
- **性能优先**: 页面加载和数据请求必须快速响应，对API进行优化，避免不必要的请求。

---

## 2. 功能需求 (Functional Requirements)

### 2.1 全局功能
- **导航栏**: 简洁的 Logo 和全局搜索框。
- **全局搜索**:
  - **API**: `GET /search/{keyword}`
  - **行为**: 用户输入哈希、区块高度或地址后，前端根据返回的 `type` 字段，自动跳转到对应的详情页。例如，`type: "tx"` -> 跳转到 `/tx/{data}`。
- **页脚 (Footer)**:
  - **链接**: 官网 (www.altcoin.host), 钱包 (wallet.altcoin.com, 标记 "Coming Soon"), GitHub, X (Twitter)。
  - **信息**: `Copyright © {current_year} Altcoin Project. All rights reserved.`

### 2.2 页面详情

**1. 首页 (Homepage)**
- **URL**: `/`
- **目的**: 提供整个区块链网络的宏观健康状况和最新动态。
- **页面组件**:
    - **A. 链上核心指标栏**:
        - **需求**: 展示“24小时交易量”、“24小时活跃地址数”、“节点数”、“平均手续费”。
        - **API Gap**: 当前 `rpc_server.py` **缺少**提供这些聚合数据的接口。我们需要定义一个新接口。
        - **建议 API**: `GET /stats/summary`
    - **B. 内存池信息卡片**:
        - **需求**: 展示当前内存池中的交易数量、总手续费等。
        - **API**: `GET /mempool/info`
    - **C. 最新区块列表**:
        - **需求**: 展示一个包含最新10-20个区块的列表。
        - **API**: `GET /block/latest/20`
        - **交互**: 列表底部有一个 "View All" 按钮，链接到 `/block/list`。
    - **D. 最新大额交易列表**:
        - **需求**: 展示最近24小时内，交易额最大的5-10笔交易。
        - **API**: `GET /tx/large/d1/1` (取第一页数据，前端按需截取)
        - **交互**: 列表底部有一个 "View All" 按钮，链接到 `/tx/list`。

**2. 区块列表页 (Block List)**
- **URL**: `/block/list`
- **目的**: 分页展示所有历史区块。
- **API**: `GET /block/list/{start}/{count}`
- **交互**: 支持标准的分页组件。

**3. 交易列表页 (Transaction List)**
- **URL**: `/tx/list`
- **目的**: 分页展示所有历史交易。
- **API**: `GET /tx/list/{start}/{take}`
- **交互**: 支持标准的分页组件。

**4. 区块详情页 (Block Detail)**
- **URL**: `/block/hash/{block_hash}` 或 `/block/height/{block_height}`
- **目的**: 展示单个区块的完整信息及其包含的所有交易。
- **API**: `GET /block/hash/{hash}` 或 `GET /block/height/{height}`

**5. 地址详情页 (Address Detail)**
- **URL**: `/address/{address}`
- **目的**: 展示特定地址的账户信息和相关的交易历史。
- **API**: `GET /address/{address}/txs/{start}/{count}`

**6. 交易详情页 (Transaction Detail)**
- **URL**: `/tx/{tx_hash}`
- **目的**: 展示单笔交易的完整信息，包括其输入和输出。
- **API**: `GET /tx/{tx_hash}`

---

## 3. 后端 API 规范与数据格式 (Data Contracts)

##### **[新增] `GET /stats/summary`**
- **描述**: 获取链上的核心摘要统计信息。
- **响应体 (JSON)**:
    ```json
    {
      "trade_volume_24h": 1234567890,
      "active_addresses_24h": 850,
      "node_count": 42,
      "avg_fee_24h": 5678
    }
    ```

##### **`GET /mempool/info`**
- **描述**: 获取内存池的摘要和交易列表。
- **响应体 (JSON)**:
    ```json
    {
      "count": 5,
      "transactions": [
        {
          "tx_hash": "e2b...c9a",
          "input_amount": 1000000,
          "output_amount": 999000,
          "fee": 1000,
          "input_addresses": ["1A..."],
          "output_addresses": ["1B...", "1C..."]
        }
      ]
    }
    ```

##### **`GET /block/latest/{count}`**
- **描述**: 获取最新的 `count` 个区块。
- **响应体 (JSON)**:
    ```json
    [
      {
        "height": 123,
        "hash": "000...abc",
        "timestamp": 1678886400,
        "tx_count": 15,
        "block_minner": "1Miner...Address",
        "reward": {
          "block_reward": 50000000,
          "fee": 12345,
          "total": 50012345
        }
      }
    ]
    ```

##### **`GET /block/list/{start}/{count}`**
- **描述**: 分页获取区块列表。
- **响应体 (JSON)**:
    ```json
    {
      "total": 12345,
      "data": [
        {
          "height": 123,
          "block_minner": "1Miner...Address",
          "tx_count": 15,
          "timestamp": 1678886400,
          "size": 180432,
          "reward": {
            "block_reward": 50000000,
            "fee": 12345,
            "total": 50012345
          }
        }
      ]
    }
    ```

##### **`GET /tx/list/{start}/{take}`**
- **描述**: 分页获取全局交易列表。
- **响应体 (JSON)**:
    ```json
    {
      "total": 98765,
      "data": [
        {
          "tx_hash": "a1b2...c3d4",
          "block_height": 123,
          "timestamp": 1678886400,
          "tx_in": [
            { "address": "1Src...Addr1", "amount": 500000 }
          ],
          "tx_out": [
            { "address": "1Dest...Addr2", "amount": 400000 },
            { "address": "1Src...Addr1", "amount": 99000 }
          ],
          "fee": 1000,
          "tx_amount": 400000
        }
      ]
    }
    ```

##### **`GET /block/hash/{hash}`**
- **描述**: 获取单个区块的完整信息。
- **响应体 (JSON)**:
    ```json
    {
      "block": { ... },
      "txs": [ ... ]
    }
    ```

##### **`GET /address/{address}/txs/{start}/{count}`**
- **描述**: 获取单个地址的信息和相关交易列表。
- **响应体 (JSON)**:
    ```json
    {
      "result": 1,
      "address": "1A...xyz",
      "balance": 12345678,
      "total_sent": 90000000,
      "total_received": 102345678,
      "tx_count": 42,
      "txs": [ ... ]
    }
    ```

##### **`GET /tx/{tx_hash}`**
- **描述**: 获取单笔交易的完整信息。
- **响应体 (JSON)**:
    ```json
    {
        "hash": "a1b2...c3d4",
        "block_hash": "000...abc",
        "block_height": 123,
        "timestamp": 1678886400,
        "tx_index": 5,
        "fee": 1000,
        "input_amount": 500000,
        "output_amount": 499000,
        "tx_amount": 400000,
        "input_count": 1,
        "output_count": 2,
        "op_return_data": "Hello Altcoin",
        "inputs": [
            { "address": "1Src...Addr1", "value": 500000 }
        ],
        "outputs": [
            { "address": "1Dest...Addr2", "value": 400000 },
            { "address": "1Src...Addr1", "value": 99000 }
        ]
    }
    ```

---

## 4. 开发与部署建议

- **前端开发代理**: 在 `package.json` 或 `vite.config.js` 中设置 `proxy`，将 `/rpc/` 前端请求代理到后端运行的RPC服务地址（如 `http://localhost:8000`），解决跨域问题。
- **组件化开发**: React开发时，将UI拆分为可复用的组件，如 `BlockCard`, `TransactionRow`, `Pagination`, `SearchBar` 等。
- **数据格式化**: 前端负责将API返回的原始数据（如Unix时间戳、tinyalt单位的金额、长哈希）格式化为用户友好的显示方式（如 "3 minutes ago"、"1.2345 ALTN"、"0xabc...def"）。
- **部署**:
    - **前端**: 使用 `npm run build` 构建静态文件，可部署在 Vercel, Netlify, 或任何静态文件服务器上。
    - **后端**: RPC Server 作为独立的服务运行。生产环境中，使用 Nginx 或其他反向代理将 `scan.altcoin.host/rpc/` 的请求转发到后端RPC服务。
