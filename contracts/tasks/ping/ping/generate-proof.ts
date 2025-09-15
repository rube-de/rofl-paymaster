import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";
import { Trie } from "@ethereumjs/trie";
import { RLP } from "@ethereumjs/rlp";
import { 
  bytesToHex, 
  concatBytes, 
  hexToBytes, 
  intToBytes,
  hexToBigInt,
  bytesToInt,
  intToHex
} from "@ethereumjs/util";
import { createBlockHeaderFromRPC } from "@ethereumjs/block";
import { Common, Sepolia, createCustomCommon, Hardfork } from "@ethereumjs/common";

// Helper function to encode transaction index for trie key
const encodeIndex = (_index: string) =>
  _index === "0x0" ? RLP.encode(Buffer.alloc(0)) : RLP.encode(bytesToInt(hexToBytes(_index as `0x${string}` ?? "0x0")));

task("generate-proof", "Generate Merkle proof for cross-chain ping verification")
  .addParam("txHash", "Transaction hash containing the Ping event")
  .addOptionalParam("logIndex", "Log index of Ping event (auto-detect if not provided)")
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;
    
    console.log("🛠️  Generating Merkle Proof");
    console.log("Transaction hash:", taskArgs.txHash);
    console.log("Network:", hre.network.name);
    
    const networkConfig = hre.network.config as any;
    if (!networkConfig.url) {
      throw new Error(`No RPC URL configured for network: ${hre.network.name}`);
    }
    
    const sourceProvider = new ethers.JsonRpcProvider(networkConfig.url);
    
    try {
      // Get transaction receipt
      console.log("📥 Fetching transaction receipt...");
      const receipt = await sourceProvider.getTransactionReceipt(taskArgs.txHash);
      
      if (!receipt) {
        throw new Error("Transaction receipt not found");
      }
      
      console.log(`  Block: ${receipt.blockNumber}, Tx index: ${receipt.index}`);
      
      // Get block header with all fields
      console.log("📦 Fetching block header...");
      const blockHex = `0x${receipt.blockNumber.toString(16)}`;
      const block = await sourceProvider.send("eth_getBlockByNumber", [blockHex, true]);
      
      if (!block) {
        throw new Error("Block not found");
      }
      
      console.log(`  Block hash: ${block.hash}`);
      
      // Find Ping log index
      let pingLogIndex = taskArgs.logIndex;
      
      if (pingLogIndex === undefined) {
        console.log("\n🔍 Auto-detecting Ping log...");
        const pingSenderInterface = new ethers.Interface([
          "event Ping(address indexed sender, uint256 indexed blockNumber)"
        ]);
        
        for (let i = 0; i < receipt.logs.length; i++) {
          try {
            const parsed = pingSenderInterface.parseLog(receipt.logs[i]);
            if (parsed && parsed.name === "Ping") {
              pingLogIndex = i;
              console.log(`  Found Ping at log index ${i}`);
              break;
            }
          } catch {
            // Not a Ping log
          }
        }
        
        if (pingLogIndex === undefined) {
          throw new Error("Ping log not found in transaction");
        }
      }
      
      // Generate real cryptographic proof using Hashi's method
      console.log("\n🧮 Generating cryptographic proof...");
      
      const chainId = Number((await sourceProvider.getNetwork()).chainId);
      
      // Configure Common for the source chain
      const common = chainId === 11155111
        ? new Common({ chain: Sepolia })
        : createCustomCommon(
            { chainId },
            Sepolia,
            { hardfork: Hardfork.Cancun, eips: [7685] }
          );
      
      // Fetch all receipts in the block
      console.log("📥 Fetching receipts...");
      const receipts = await Promise.all(
        block.transactions.map(async (tx: any) => {
          const txHash = typeof tx === 'string' ? tx : tx.hash;
          return await sourceProvider.send("eth_getTransactionReceipt", [txHash]);
        })
      );
      console.log(`  Found ${receipts.filter(r => r).length} receipts`);
      
      // Encode all receipts for the trie
      console.log("🔐 Encoding receipts...");
      const encodedReceipts = receipts.map((_receipt: any) => {
        const type = Number(hexToBigInt(_receipt.type || "0x0"));
        
        // Standard receipt encoding
        const encoded = RLP.encode([
          _receipt.status === "0x1" ? hexToBytes("0x01") : Uint8Array.from([]),
          hexToBytes(_receipt.cumulativeGasUsed),
          hexToBytes(_receipt.logsBloom),
          _receipt.logs.map((_log: any) => {
            return [hexToBytes(_log.address), _log.topics.map(hexToBytes), hexToBytes(_log.data)]
          }),
        ]);
        
        // Add transaction type prefix if not legacy (type 0)
        if (type === 0) return encoded;
        return concatBytes(intToBytes(type), encoded);
      });
      
      // Build receipt trie
      console.log("🌳 Building Merkle trie...");
      const trie = new Trie();
      
      await Promise.all(
        receipts.map((_receipt: any, _index: number) => 
          trie.put(encodeIndex(_receipt.transactionIndex), encodedReceipts[_index])
        )
      );
      
      // Verify trie root
      const calculatedRoot = bytesToHex(trie.root());
      if (calculatedRoot !== block.receiptsRoot) {
        throw new Error(`Trie root mismatch! Calculated: ${calculatedRoot}, Block: ${block.receiptsRoot}`);
      }
      
      // Generate Merkle proof
      const receiptKey = encodeIndex(intToHex((receipt as any).index));
      const merkleProof = await trie.createProof(receiptKey);
      
      // Create block header from RPC data
      const blockHeader = createBlockHeaderFromRPC(block, { common });
      const encodedBlockHeader = bytesToHex(blockHeader.serialize());

      // Verify header hash matches
      const headerHash = ethers.keccak256(hexToBytes(encodedBlockHeader));
      if (headerHash !== block.hash) {
        throw new Error(`Header hash mismatch. Calculated ${headerHash} vs RPC ${block.hash}`);
      }
      
      const blockNumber = Number(receipt.blockNumber);
      const logIndex = pingLogIndex;
      
      // Create proof structure for Hashi
      const proof = [
        chainId,
        blockNumber,
        encodedBlockHeader,
        0, // ancestralBlockNumber (not used)
        [], // ancestralBlockHeaders (not used)
        merkleProof.map(node => bytesToHex(node)),
        bytesToHex(encodeIndex(intToHex((receipt as any).index))),
        logIndex
      ];
      
      // Save proof to file
      const proofPath = "proof.json";
      require("fs").writeFileSync(proofPath, JSON.stringify(proof, null, 2));
      
      console.log("\n✅ Proof generated successfully!");
      console.log("📋 Summary:");
      console.log(`  Chain ID: ${chainId}`);
      console.log(`  Block Number: ${blockNumber}`);
      console.log(`  Transaction Index: ${Number(receipt.index)}`);
      console.log(`  Log Index: ${logIndex}`);
      console.log(`  Merkle Proof Elements: ${merkleProof.length}`);
      console.log(`  Saved to: ${proofPath}`);
      
      console.log("\n💡 Next step:");
      console.log(`bunx hardhat relay-message --receiver <RECEIVER_ADDRESS> --proof ${proofPath} --network <TARGET_NETWORK>`);
      
      return {
        proof,
        blockHash: block.hash,
        blockNumber,
        transactionIndex: Number(receipt.index),
        logIndex
      };
      
    } catch (error) {
      console.error("❌ Error generating proof:", error);
      throw error;
    }
  });