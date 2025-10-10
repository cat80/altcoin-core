# Thoughts on and Implementation of Block Reorganization

**Author: cat80**

**Date: October 10, 2025**

### 1. Project Background and Plan

#### 1.1 Current Progress

After returning from a trip, I've resumed the development of my altcoin project. Following a 10-day hiatus, I'm picking things up again. Given the increasing complexity of the project, I find it necessary to document some project-related notes and outline the future development direction, recording key design decisions along the way.

Currently, the project has completed its core standalone functionalities and can successfully mine blocks locally. The specific implementations are as follows:

-   **Data Storage**:
    -   Complete block data (`txin`, `txout`, `transaction`, `block header`, `block`) is serialized and stored using a custom binary format.
    -   **SQLite** is used to store the block index (`BlockIndex`), which includes metadata such as block headers, height, total work, and chain status. Key fields are indexed.
    -   **RocksDB** is used as a high-performance Key-Value store to maintain the UTXO set (`ChainState`).
-   **Core Functionality**:
    -   Supports the creation of a genesis block with a customizable difficulty.
    -   Implemented logic for receiving and validating new blocks, including header validity, Proof-of-Work (PoW) verification, and UTXO validation for transactions.
    -   The system can append validated blocks to the local blockchain file and synchronously update the `BlockIndex` and `ChainState`.

#### 1.2 Future Plans

The current single-node mining model is stable. The next focus is to implement the core consensus logic for a decentralized network, laying a solid foundation for building the P2P network.

-   **Top Priority**: Implement a robust **Block Reorganization** mechanism.
-   **Ultimate Goal**: Implement the P2P network layer, turning the project into a truly operational blockchain that can synchronize and reach consensus among multiple nodes.

---

### 2. Design of Block Reorganization

Block reorganization is the soul of the PoW consensus algorithm. In a distributed network, forks occur temporarily due to network latency, as nodes receive blocks in different orders. The reorganization mechanism ensures that the network eventually converges on a single "longest/heaviest" chain.

#### 2.1 The Core Reorganization Process

When a node receives a new block whose parent is not the tip of the current main chain, a potential reorganization process is triggered. The entire process can be broken down into these key steps:

1.  **Fork Detection**: The new block's `prev_block_hash` exists in the `BlockIndex` but is not the main chain tip, confirming it's a fork.
2.  **Work Comparison**: Calculate and compare the total work of the new forked chain with the current main chain. A reorganization is initiated only if the new chain's total work is **strictly greater** than the current main chain's.
3.  **Locating the Common Ancestor**: Efficiently find the Lowest Common Ancestor (LCA) of the old and new chains.
4.  **Disconnecting Old Blocks**: Starting from the current main chain tip, roll back block by block towards the common ancestor, reverting the changes these blocks made to the `ChainState` (UTXO set).
5.  **Connecting New Blocks**: Starting from the block after the common ancestor, apply the blocks from the new chain one by one, committing their changes to the `ChainState`.
6.  **Atomic State Update**: Ensure that the updates to `BlockIndex` and `ChainState` either all succeed or all fail to prevent the system from entering an inconsistent state.

#### 2.2 Key Technical Challenges and Solutions

##### 2.3.1 Efficiently Finding the Common Ancestor

Traversing and comparing two long chains is highly inefficient. We will adopt an efficient algorithm:
1.  First, bring the pointers of both chains to the same height. The pointer on the taller chain is moved backward until its height matches the other.
2.  Then, move both pointers backward in lockstep, one block at a time.
3.  When both pointers refer to the same block, that block is the LCA.
The time complexity of this algorithm is proportional to the depth of the fork, making it nearly instantaneous for common, short forks. The first version will query the database directly, ensuring the `block_hash` and `prev_block_hash` fields are indexed for reasonable performance. For optimal performance later on, the `BlockIndex` will be loaded into an in-memory dictionary at startup, enabling O(1) hash lookups.

##### 2.3.2 State Rollback and Application

This is the core operation of a reorg, directly affecting the UTXO set in RocksDB:
-   **`connect_block`**: (Already implemented) For each transaction in a block, consume the UTXOs corresponding to its `txin`s and create new UTXOs from its `txout`s.
-   **`disconnect_block`**: This is the reverse operation. For each transaction in a block, it must:
    -   Delete all `txout`s created by the transaction.
    -   "Revive" the `txout`s consumed by the transaction's `txin`s, adding them back to the UTXO set.

##### 2.3.3 Ensuring Atomicity Across Databases

`BlockIndex` (SQLite) and `ChainState` (RocksDB) are separate databases, making true distributed transactions impossible. We will adopt a **highly available and recoverable** strategy to approximate atomicity:

1.  **Isolated Operations and Validate-First Principle**: 
    - **Create an In-Memory View**: All UTXO changes (both `disconnect` and `connect`) are first performed on an in-memory cache layer (`UTXOViewCache`). This view acts as a snapshot of the underlying database at the beginning of the operation.
    - **Rollback to Common Ancestor**: The `disconnect` operations are executed on the `UTXOViewCache`, rolling its state back to the common ancestor.
    - **Connect and Validate New Chain**: The `connect` operations are then executed on the **same `UTXOViewCache`**. During this process, every transaction in each new block is validated against the **current state of the `UTXOViewCache`**.
    - **Discard on Failure**: If any transaction fails validation during the connection process (e.g., a double-spend), the entire `UTXOViewCache` object is simply discarded, and the reorg is aborted. This design ensures that the persistence layer is only touched after 100% successful validation, preventing database corruption.

2.  **Metadata-First Commit**:
    a. Begin a SQLite transaction.
    b. Within the transaction, update the status (`is_main_chain` flag) of the blocks on the old and new chains in the `BlockIndex`.
    c. **Commit the SQLite transaction**.
    d. If the SQLite commit is successful, generate a `WriteBatch` from all the changes in the `UTXOViewCache` and **write it to RocksDB in a single operation**.

3.  **Fault Recovery**: With this sequence, if the program crashes between steps (c) and (d), the `BlockIndex` will point to the new chain while the `ChainState` remains on the old one. This is a **clearly detectable error**. We will add a consistency check at startup (e.g., checking if the coinbase UTXO of the main chain tip exists). If an inconsistency is found, the system will prompt the user or automatically trigger a **re-index (`-reindex`)**, replaying all blocks from genesis to rebuild a correct `ChainState`.

##### 2.3.4 Deferred Validation of Sidechain Blocks

A key question is when to validate the transactions in a sidechain block. The answer is during the "connect" phase of the reorganization.
-   **Reception Phase**: When a sidechain block is received, only context-free checks (e.g., PoW, block size) are performed. The block is then stored without its UTXOs being validated.
-   **Reorganization Phase**: After the `ChainState` has been rolled back to the common ancestor's state within the in-memory view, we have the **correct context**. At this point, during the process of connecting the new chain's blocks, a full UTXO validation is performed for every transaction. If any transaction is found to be invalid, the entire fork is considered illegal, and the reorg is aborted.

---

### 3. Concurrency Model and System Integration

To safely integrate the reorganization logic into a future multi-threaded P2P network environment, we will adopt the following concurrency model:

1.  **Task Queue and Single-Threaded Processing**: A global, thread-safe **task queue** will be established. All requests that modify the chain state (e.g., "process new block," "handle reorg") will be placed into this queue as tasks. A **single, dedicated "blockchain manager" thread** will act as the consumer, processing these tasks serially. This fundamentally prevents concurrent write access to critical data (`BlockIndex`, `ChainState`).

2.  **Event-Driven Model and Module Decoupling (Event Bus)**: A global **event bus** will be established. When the manager thread successfully processes a task that results in a chain state change (e.g., a successful reorg), it will publish an **event** (e.g., `new_block_tip`). Other modules in the system (like the `Miner`, `Wallet`) can subscribe to these events. When the `Miner` receives the `new_block_tip` event, it will immediately interrupt its current mining job (based on the old `prevhash`) and start a new job based on the new chain tip information. This achieves efficient decoupling and near-instantaneous response.

---

### 4. Testing Plan

To ensure the robustness and correctness of the reorganization logic, the following core test case will be designed.

#### 4.1 Test Case: `test_blockchain_reorg`

This test case simulates a complete fork competition and reorganization, verifying the final consistency of the chain state.

**Test Steps:**

1.  **Build the Initial Main Chain**
    -   Create a blockchain instance with a genesis block.
    -   Mine and add 9 new blocks (Block #1 to #9) to form a main chain of length 10.
    -   During this process, create a transaction chain: a transaction in Block #N+1 will spend the coinbase output of Block #N, sending it to an address `Addr_Main_N`.

2.  **Build a Longer Side Chain**
    -   Designate Block #4 of the main chain as the fork point (`fork_block`).
    -   Based on `fork_block`, mine and add 6 new blocks (SideBlock #5 to SideBlock #10) to form a side chain with a total height of `4 (from main) + 6 = 10`.
    -   **Note**: The total work of the side chain should now be greater than or equal to the old main chain (depending on whether difficulty changes).
    -   Similarly, create a transaction chain within the side chain: a transaction in SideBlock #N+1 will spend the coinbase output of SideBlock #N, sending it to an address `Addr_Side_N`.
    -   Mine one more block, SideBlock #11, to make its total work definitively **greater** than the main chain.

3.  **Trigger the Reorganization**
    -   Submit the last block of the side chain (SideBlock #11) to the blockchain instance for processing.
    -   As the chain containing SideBlock #11 has more total work, the system should automatically trigger and complete a reorganization.

4.  **Verify the Result**
    -   **Chain Structure Verification**:
        -   Confirm that the current main chain tip's hash is **equal to** the hash of SideBlock #11.
        -   Confirm that the current main chain height is 11.
        -   Confirm in the `BlockIndex` that the status of the old main chain's Blocks #5 to #9 has been changed to "side chain," while the status of SideBlocks #5 to #11 has been changed to "main chain."
    -   **UTXO Set Verification**:
        -   **Verify Old Chain State is Rolled Back**: Check that the UTXOs previously sent to `Addr_Main_5` through `Addr_Main_9` **no longer exist** in the `ChainState`. These transactions should have been reverted when the blocks were disconnected.
        -   **Verify New Chain State is Applied**: Check that the UTXOs sent to `Addr_Side_5` through `Addr_Side_10` **exist and are unspent** in the `ChainState`.
        -   **Spot Check**: Randomly select a regular transaction from one of the disconnected blocks and verify its output UTXO does not exist. Randomly select a regular transaction from one of the new main chain blocks and verify its output UTXO exists.
        -   **Verify Pre-Fork State is Unchanged**: Verify that the state of UTXOs related to the genesis block through Block #4 remains unchanged.

This test case will provide comprehensive coverage of the chain structure switch and the precise rollback and application of the UTXO state during a reorganization, ensuring the correctness of the core consensus logic.

### 5. Summary and Outlook

Through this design, we will build a robust, efficient, and thread-safe block reorganization mechanism. This mechanism not only correctly handles the core consensus logic of the blockchain but also establishes a clean, extensible architecture for future integration of a P2P network and more complex features by introducing a task queue and an event bus. Upon completing this step, the project will be ready to move towards a truly decentralized network.