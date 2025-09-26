# AltCoin: A Foundational Blockchain Protocol for Learning and Practice

**Whitepaper v0.1**

**Author:cat80**

**Date: September 26, 2025**

---

### 1. Abstract

This paper outlines the design and implementation of a foundational blockchain protocol named AltCoin. AltCoin is designed to be a fully-functional, hands-on cryptocurrency platform that adheres to Bitcoin's UTXO model and Proof-of-Work consensus. The core objective of this project is not to create a new financial asset, but to provide developers and researchers with a transparent, full-stack environment that they can build from scratch, thereby gaining a deep understanding of the underlying principles of blockchain technology. Through an end-to-end implementation, from the core protocol to the application ecosystem, we aim to bridge the gap between theoretical knowledge and engineering practice.

### 2. Introduction

With the rapid development of blockchain technology, the complexity of its underlying principles presents a significant challenge for learners. Existing learning resources often focus on theoretical descriptions or high-level application development, leaving learners without an intuitive and profound understanding of core mechanisms such as internal interaction logic, data flow, and security guarantees. We believe that the best way to understand a complex system is to build it yourself.

The AltCoin project was born from this philosophy. It is an open-source learning project that guides developers to progressively implement all core components of a blockchain from scratch using a modern programming language like Python. This project is not merely a theoretical model but a runnable, interactive, and extensible platform for practice. Its ultimate goal is to empower participants with a first-principles understanding and the engineering confidence to master this complex technology.

### 3. Core Protocol

The AltCoin protocol is designed in strict adherence to the foundational principles established by Satoshi Nakamoto in the Bitcoin whitepaper.

**3.1 Network**

The AltCoin network is a decentralized peer-to-peer (P2P) network through which nodes synchronize transaction and block data to collectively maintain a globally consistent ledger.
* **Node Discovery**: New nodes bootstrap by connecting to a set of hardcoded seed nodes to obtain an initial list of peers. Subsequently, nodes dynamically maintain and expand their peer lists by exchanging address information.
* **Message Protocol**: To achieve efficient communication and reduce bandwidth redundancy, nodes use a custom binary message protocol. Communication follows the "Inventory-Getdata" model: a node first announces new data (transactions or blocks) it possesses via an `inv` message. Other nodes, after confirming the data does not exist locally, request it using a `getdata` message.
* **API Service**: Each full node will expose a JSON-RPC interface via a separate HTTP server to allow for interaction with ecosystem applications like wallets and block explorers.

**3.2 Consensus**

AltCoin adopts **Proof-of-Work (PoW)** as its consensus algorithm to ensure network security and Sybil attack resistance.
* **3.2.1 Mining Algorithm**: Utilizes the SHA-256 hash algorithm. Miners must continuously alter the Nonce in the block header and perform a double SHA-256 hash on the header until a hash value is found that is less than the current difficulty target.
* **3.2.2 Difficulty Adjustment**: To maintain a stable block time (targeting 1 minutes), the network difficulty is adjusted every **2,016** blocks. The adjustment algorithm compares the actual time taken for the previous period against the theoretical time and increases or decreases the difficulty accordingly.
* **3.2.3 Consensus Rules**: Follows the longest chain principle (Nakamoto Consensus). In the event of a chain fork, all honest nodes will always choose to extend the chain with the most cumulative work as the main chain.
* **3.2.4 Verification Rules**: Before any transaction or block is accepted and relayed by a node, it must pass a series of rigorous checks. These rules act as the "firewall" for the AltCoin network, defending against invalid data and malicious attacks.
    * **Transaction Verification Checklist:**
        1.  **Syntax Check**: The binary format of the transaction is correct and deserializes successfully.
        2.  **Structural Check**: The lists of inputs and outputs are non-empty.
        3.  **Value Check**: All output amounts must be non-negative.
        4.  **Total Amount Check**: The total input amount must be greater than or equal to the total output amount.
        5.  **Input Validity (for each input):**
            * The referenced UTXO exists in the current unspent set (prevents double-spending).
            * The `unlocking_script` successfully validates the `locking_script` of the referenced UTXO. This typically involves signature and public key verification.
    * **Block Verification Checklist:**
        1.  **Structural Check**: The block's data structure conforms to the protocol specification.
        2.  **PoW Check**: The block hash value is less than the current difficulty target.
        3.  **Timestamp Check**: The timestamp is within a reasonable range (greater than the previous block's and not too far in the future).
        4.  **Coinbase Transaction Check**: The first transaction in the block must be a valid Coinbase transaction.
        5.  **Transaction List Check**: All transactions within the block must pass the transaction verification checklist above.
        6.  **Merkle Root Check**: The Merkle root in the block header can be correctly calculated from the list of transactions in the block body.

**3.3 Data Structure**

* **3.3.1 Transaction**: AltCoin uses the **Unspent Transaction Output (UTXO)** model.
    * **Inputs**: Each input points to a pre-existing UTXO and proves ownership by providing an `unlocking_script`. An input is uniquely identified by `(previous_tx_hash, output_index, unlocking_script)`.
    * **Outputs**: Each output creates a new UTXO, containing an amount (`value`) and a `locking_script`, which defines the conditions for spending that UTXO.
    * **3.3.1.1 Scripting Language**: To verify the legality of a transaction, AltCoin uses a minimalistic, stack-based scripting language. You can think of it as an "unlocking" process: the `unlocking_script` (the key) provided by the spending transaction and the `locking_script` (the lock) from the UTXO it references are combined. The script engine executes the instructions one by one. Only when all instructions are finished and the final value on top of the stack is `TRUE` does it signify a successful "unlock," and the transaction is verified.
        * **Basic Opcodes:**
            * `OP_DUP`: Duplicates the top item on the stack.
            * `OP_SHA256`: Hashes the top item on the stack using SHA256.
            * `OP_EQUALVERIFY`: Compares the top two items on the stack. If they are equal, they are popped. If not, the script fails.
            * `OP_CHECKSIG`: Verifies the transaction signature. It uses the public key and signature from the top of the stack to verify a specific part of the transaction. This is the core opcode for guaranteeing ownership.

* **3.3.2 Block**: A block is a collection of transactions, composed of a block header and a block body.
    * **Block Header**: A compact 80-byte structure containing the version, previous block hash, Merkle root, timestamp, difficulty target (Bits), and Nonce.
    * **Block Body**: Contains the full list of all transactions included in the block.
    * **Merkle Tree**: The hashes of all transactions in a block are constructed into a Merkle tree. Its root hash (Merkle Root) is recorded in the block header to efficiently verify the integrity of the transaction list.

* **3.3.3 Genesis Block**:
    * The Genesis Block is the "singularity" of the AltCoin universe, the sole ancestor of all other blocks. It serves as the chain's root of trust and is hardcoded directly into the client software. As the very first block, its `PrevBlockHash` field is all zeros.

* **3.3.4 Coinbase Transaction**:
    * Each block begins with a special Coinbase transaction. This transaction is how miners "pay themselves," bundling the fixed block reward (e.g., 50 ALT) with the transaction fees contributed by all other transactions in the block.
    * **Special Characteristics**: A Coinbase transaction has no regular inputs. Its `inputs` field contains a special `coinbase` data area where miners can record arbitrary information (like an `extranonce`). Its output is the reward received by the miner.

### 4. Economic Model

AltCoin has a clear monetary issuance and incentive policy.

* **Total Supply**: To simulate the scarcity of real cryptocurrencies, the total supply is capped at **21 million**.
* **Block Reward**: The initial block reward is set to **50 ALT**.
* **Halving**: To implement a deflationary model, the block reward is halved every **100,000** blocks until the reward approaches zero.
* **Transaction Fees**: The difference between the total input and total output amounts of a transaction constitutes the transaction fee. This fee, along with the block reward, serves as the incentive for the miner who successfully includes the transaction in a block.

### 5. Ecosystem Roadmap

The development of this project will follow three phases to progressively build a complete ecosystem:

* **Phase 1: The Core**: Implement a stable, fully-functional full node client. Features will include P2P network communication, mining, transaction and block validation and propagation, and providing a basic RPC API.
* **Phase 2: The Explorer**: Develop a web-based block explorer. Users can query real-time on-chain data such as blocks, transactions, and address balances, achieving full data transparency.
* **Phase 3: The Wallet**: Develop a user-friendly wallet application (desktop or web). Users can manage their private keys, check balances, and construct and broadcast transactions. A browser extension wallet could be planned for the future.

### 6. Conclusion

AltCoin is a non-commercial project with education and research as its primary goals. By providing a complete, hands-on blueprint—from the underlying protocol to the application layer—it aims to help developers and tech enthusiasts see through the complexity of the blockchain world and truly master its core design principles and engineering implementation. We believe that this exploration from first principles is the most solid path toward future technological innovation.