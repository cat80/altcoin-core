
# Altcoin-Core: A Complete Blockchain Project Built from Scratch

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

English | [简体中文](./README.zh-CN.md)

**Source Code:**
*   **Backend (This Project):** [https://github.com/cat80/altcoin-core/](https://github.com/cat80/altcoin-core/)
*   **Frontend (Blockchain Explorer):** [https://github.com/cat80/altcoin-scan](https://github.com/cat80/altcoin-scan)

---

**Altcoin-Core** is a blockchain system built from scratch without relying on any existing blockchain frameworks like Substrate or Cosmos SDK. The project fully implements modules ranging from the underlying core storage, P2P network, and consensus mechanism to the upper-layer RPC interface and command-line tools.

This project aims to practice and demonstrate the core technologies and engineering implementation of a complete blockchain system. Currently, a stable **testnet** has been deployed, complete with an online **blockchain explorer** and RPC service.

### ✨ **Live Services (Testnet)**

*   **Blockchain Explorer:** [https://www.altcoin.host](https://www.altcoin.host) (with a built-in faucet)
*   **RPC Service Node:** [https://rpc.altcoin.host](https://rpc.altcoin.host)
*   **P2P Seed Nodes:**
    *   `node1.altcoin.host:17890`
    *   `node2.altcoin.host:17890`

#### **Explorer Screenshots**

| Index Page | Block Details |
| :---: | :---: |
| <img src="doc/images/scan-index-snapshot.png" alt="Index Page Screenshot" width="450"/> | <img src="doc/images/scan-block-details-snapshot.png" alt="Block Details Screenshot" width="450"/> |
| **Transaction Details** | **Faucet** |
| <img src="doc/images/scan-tx-details-snapshot.png" alt="Transaction Details Screenshot" width="450"/> | <img src="doc/images/scan-claim-snapshot.png" alt="Faucet Screenshot" width="450"/> |

---

## 🚀 Architecture and Core Module Design

### 1. **Core Layer (`core`)**
Responsible for defining the basic data structures (Block, Transaction) and core business logic of the blockchain.
*   **Chain State & Reorganization**: Designed with data consistency in mind, especially with detailed handling of the chain reorganization (Reorg) process. When handling forks, all operations on the UTXO set are first performed in a temporary memory view (`ChainStateCacheView`). Only after the new chain is fully validated are the changes atomically applied to the main state. `UndoRecord`s are also designed to ensure the accuracy of rollback operations.
*   **Component-based Responsibility**: The `Blockchain` class acts as a coordinator, orchestrating multiple components with clear responsibilities, such as `BlockStorage`, `BlockIndex`, `ChainState`, and `BlockValidator`.

### 2. **P2P Network Layer (`p2p`)**
Responsible for node discovery, communication, and data synchronization, featuring a layered design and multiple communication modes.
*   **Event-Driven & Decoupled**: An asynchronous event bus (`EventBus`) based on `asyncio` is implemented for inter-module communication, avoiding direct calls between modules.
*   **Hybrid Communication Modes**: Supports both the **Gossip protocol** for information dissemination and a **Request-Response** pattern for precise data requests.
*   **Background Connection Maintenance**: The `PeerManager` includes a background task (`_maintenance_loop`) that periodically checks and maintains a target number of node connections to ensure the node's connectivity within the network.

### 3. **Consensus Layer (`consensus`)**
Responsible for the generation and validation of new blocks, i.e., mining.
*   **PoW Consensus**: Implements a Proof-of-Work based consensus algorithm.
*   **Multi-Process Mining**: To overcome the limitations of Python's Global Interpreter Lock (GIL) on CPU-intensive tasks, the mining process is implemented using a **Process Pool (`ProcessPoolExecutor`)**. This allows mining tasks to run in parallel, effectively utilizing the server's multi-core CPU resources.

### 4. **Mempool (`mempool`)**
Serves as a buffer for transactions before they are included in the blockchain.
*   **Transaction Collection & Validation**: Responsible for collecting broadcasted transactions from the P2P network and performing initial validation of their signatures, structure, and UTXO validity.
*   **Transaction Packaging**: Provides a list of pending transactions for miners in the consensus layer to select from when building a new block.

### 5. **Indexer (`indexer`)**
Designed to provide fast data query capabilities for the RPC interface.
*   **Data Parsing & Indexing**: The indexer listens for new block events, parses each transaction in the block, and creates indices based on key information such as addresses and transaction hashes. This avoids the inefficiency of traversing the entire blockchain for queries.

### 6. **RPC Interface Layer (`rpc`)**
Provides a standard JSON-RPC interface, acting as a bridge between the external world and the blockchain.
*   **API Design**: Built with **FastAPI**, it offers various interfaces, including querying block, transaction, and address information, for upper-layer applications like wallets and explorers to call.
*   **Service Startup**: The RPC service runs in the same process as the P2P service but listens on a different port, calculated as `1000 + p2p_port % 100`.

### 7. **Application Layer (Wallet & Frontend)**
*   **Command-Line Wallet (`cmd`)**: A feature-rich local command-line tool that interacts with the RPC interface to perform operations like creating accounts, checking balances, and initiating transfers.
*   **Blockchain Explorer (`altcoin-scan`)**: This is a separate **React** frontend project that fetches on-chain data via the public RPC service node and displays it in a user-friendly graphical interface. It is completely decoupled from the `altcoin-core` backend and serves as a typical application case for the RPC interface.

---

## Local Quick Start Guide

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/cat80/altcoin-core.git
    cd altcoin-core
    ```

2.  **Switch to the testnet branch**:
    The `testnet` branch contains the necessary configurations to connect to the live test network.
    ```bash
    git checkout testnet
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Start the node**:
    ```bash
    python src/main.py
    ```
    *   The node will run the P2P service on port `17890` by default.
    *   The RPC service will run on port `8090` by default.

---

## Commit Message Convention

This project follows a commit message convention to maintain a clear history. Commit messages should be in the format:
`<type>: <subject>`

Commonly used `type`s include:
*   **feat**: A new feature
*   **fix**: A bug fix
*   **docs**: Documentation only changes
*   **style**: Changes that do not affect the meaning of the code (white-space, formatting, etc)
*   **refactor**: A code change that neither fixes a bug nor adds a feature
*   **test**: Adding missing tests or correcting existing tests
*   **chore**: Changes to the build process or auxiliary tools and libraries

---

## Node Running Configuration

For users who want to run a node on a server for the long term, the following minimum configuration is recommended:
*   **CPU**: 2 Cores
*   **Memory**: 4 GB
*   **Storage**: 50 GB SSD
*   **OS**: Linux (Ubuntu, CentOS, etc.)

---

## 📖 Core RPC API Examples

The project provides a series of RPC interfaces for interacting with the blockchain. Below are examples of some core interfaces. For a more detailed list, please refer to `src/rpc/rpc_server.py`.

*   **Broadcast a Raw Transaction**
    *   `POST /rpc/tx/send`
    *   **Body**: `{ "hex": "<raw_tx_hex>" }`
    *   **Function**: Receives a hex-encoded raw transaction, validates it, adds it to the mempool, and broadcasts it to the network.

*   **Get Block Information by Height**
    *   `GET /rpc/block/height/{height}`
    *   **Function**: Returns detailed information for the block at the specified height, including the block header and a list of all transactions.

*   **Get Address Information**
    *   `GET /rpc/address/{address}`
    *   **Function**: Returns summary information for the specified address, including the current balance, total sent, total received, and transaction count.

*   **Get Available UTXOs for an Address**
    *   `GET /rpc/address/{address}/utxos`
    *   **Function**: Returns all unspent transaction outputs (UTXOs) for the specified address, which is essential for building new transactions.

> For the complete interface definitions and implementation, please refer directly to the `src/rpc/rpc_server.py` file.

---

## License

This project is licensed under the MIT License.
