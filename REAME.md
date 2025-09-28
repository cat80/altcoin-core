# AltCoin Project

![Language](https://img.shields.io/badge/language-Python-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

[English](./README.md) | [中文](./README.zh-CN.md)

## About The Project

AltCoin is a foundational blockchain protocol implemented from scratch in Python for educational purposes. Its primary goal is not to create a new financial asset, but to serve as a transparent, hands-on, full-stack platform for deeply understanding the first principles of blockchain technology.

This project covers the entire lifecycle of a blockchain system, from the core data structures and consensus mechanisms to the application ecosystem, including a node, an explorer, and a wallet.

### Project Philosophy

> We firmly believe that the best way to understand a complex system is to build it from the ground up.

This project aims to bridge the significant gap between abstract blockchain theory and concrete engineering practice.

## Core Features

* **Consensus:** Proof-of-Work (PoW) using Double-SHA256 (SHA256d).
* **Data Model:** Unspent Transaction Output (UTXO) model.
* **Storage:** Compact binary format for on-disk block storage.
* **Networking:** A simplified P2P network layer with a user-facing JSON-RPC API.
* **Cryptography:** ECDSA on the `SECP256k1` curve for digital signatures.
* **Addresses:** Ethereum-style `0x` prefixed hexadecimal addresses with EIP-55 checksum validation.

## Project Structure

```
altcoin-core/
├── doc/                # Documentation (Whitepaper, API specs)
├── src/                # Source code
│   ├── core/           # Core data structures (Block, Transaction)
│   ├── consensus/      # Consensus logic (PoW)
│   ├── network/        # P2P communication
│   ├── api/            # JSON-RPC API server
│   ├── storage/        # On-disk storage management
│   ├── utils/          # Cryptographic and serialization utilities
│   └── main.py         # Main entry point to run a node
├── test/               # Unit and integration tests
└── requirements.txt    # Project dependencies
```

## Getting Started

Follow these steps to get your local node up and running.

### Prerequisites

* Python 3.8+

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone [https://github.com/](https://github.com/)[YOUR_USERNAME]/altcoin-core.git
    cd altcoin-core
    ```
2.  **Create and activate a virtual environment:**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

### Running the Node

1.  **Run the tests to ensure everything is working:**
    ```sh
    python -m unittest discover
    ```
2.  **Start your node:**
    ```sh
    python src/main.py
    ```

## Project Roadmap

The development of AltCoin is planned in three main phases:

1.  **Phase 1: The Core Node**
    * Implement a stable, fully functional node client with P2P networking, mining, and transaction/block validation capabilities.
2.  **Phase 2: The Block Explorer**
    * Develop a web-based block explorer to provide a transparent window into the blockchain's real-time state.
3.  **Phase 3: The Wallet**
    * Create a user-friendly wallet application (Desktop/Web) for managing keys, checking balances, and creating transactions.

## License

Distributed under the MIT License. See `LICENSE` file for more information.