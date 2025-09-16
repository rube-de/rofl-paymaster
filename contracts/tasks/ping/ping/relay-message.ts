import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";
import * as fs from "fs";

// Hashi proof format is an array: [chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders, receiptProof, transactionIndex, logIndex]
type ProofData = [number, number, string, number, string[], string[], string, number];

task("relay-message", "Relay cross-chain ping message using cryptographic proof")
  .addParam("proof", "Proof data (JSON file path or inline JSON string)")
  .addOptionalParam("receiver", "PingReceiver contract address on destination chain", "0x1f54b7AF3A462aABed01D5910a3e5911e76D4B51")
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;
    
    console.log("🌉 Relaying cross-chain message");
    console.log("Receiver address:", taskArgs.receiver);
    console.log("Network:", hre.network.name);
    
    try {
      // Parse proof data
      let proofData: ProofData;
      
      if (taskArgs.proof.startsWith('{')) {
        // Inline JSON string
        console.log("📄 Parsing inline proof data...");
        proofData = JSON.parse(taskArgs.proof);
      } else {
        // File path
        console.log("📁 Loading proof from file:", taskArgs.proof);
        if (!fs.existsSync(taskArgs.proof)) {
          throw new Error(`Proof file not found: ${taskArgs.proof}`);
        }
        const proofJson = fs.readFileSync(taskArgs.proof, 'utf8');
        proofData = JSON.parse(proofJson);
      }
      
      // Validate proof structure (array format)
      console.log("🔍 Validating proof structure...");
      if (!Array.isArray(proofData) || proofData.length !== 8) {
        throw new Error("Invalid proof data: must be array with 8 elements [chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders, receiptProof, transactionIndex, logIndex]");
      }
      
      const [chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders, receiptProofArray, transactionIndex, logIndex] = proofData;
      
      if (typeof chainId !== 'number' || typeof blockNumber !== 'number' || typeof blockHeader !== 'string') {
        throw new Error("Invalid proof data: chainId and blockNumber must be numbers, blockHeader must be string");
      }
      
      if (!Array.isArray(receiptProofArray) || !Array.isArray(ancestralBlockHeaders)) {
        throw new Error("Invalid proof data: receiptProof and ancestralBlockHeaders must be arrays");
      }
      
      if (typeof logIndex !== 'number' || typeof transactionIndex !== 'string') {
        throw new Error("Invalid proof data: logIndex must be number, transactionIndex must be string");
      }
      
      console.log("  ✅ Proof structure valid");
      console.log("  Source Chain ID:", chainId);
      console.log("  Block Number:", blockNumber);
      console.log("  Log Index:", logIndex);
      console.log("  Receipt Proof Elements:", receiptProofArray.length);
      console.log("  Ancestral Headers:", ancestralBlockHeaders.length);
      
      // Get PingReceiver contract
      console.log("\n📡 Connecting to PingReceiver...");
      const PingReceiver = await ethers.getContractFactory("PingReceiver");
      const pingReceiver = PingReceiver.attach(taskArgs.receiver);
      
      // Verify contract exists and has the expected interface
      try {
        await pingReceiver.getAddress();
        console.log("  ✅ Contract found at address:", taskArgs.receiver);
      } catch (error) {
        throw new Error(`Failed to connect to PingReceiver at ${taskArgs.receiver}: ${error}`);
      }
      
      // Format proof for contract call (convert array to struct format expected by PingReceiver)
      console.log("\n🔧 Formatting proof for contract call...");
      const receiptProof = {
        chainId: chainId,
        blockNumber: blockNumber,
        blockHeader: blockHeader,
        ancestralBlockNumber: ancestralBlockNumber,
        ancestralBlockHeaders: ancestralBlockHeaders,
        receiptProof: receiptProofArray,
        transactionIndex: transactionIndex,
        logIndex: logIndex
      };
      
      console.log("  ✅ Proof formatted for ReceiptProof struct");
      
      // Call receivePing function
      console.log("\n📤 Submitting proof to PingReceiver.receivePing()...");
      console.log("  This will verify the proof cryptographically and record the ping");
      
      const tx = await pingReceiver.receivePing(receiptProof);
      console.log("  Transaction hash:", tx.hash);
      
      // Wait for confirmation
      console.log("⏳ Waiting for transaction confirmation...");
      const receipt = await tx.wait();
      
      if (receipt.status === 1) {
        console.log("✅ Message relayed successfully!");
        console.log("  Block number:", receipt.blockNumber);
        console.log("  Gas used:", receipt.gasUsed.toString());
        
        // Parse events
        const events = receipt.logs.map(log => {
          try {
            return pingReceiver.interface.parseLog(log);
          } catch {
            return null;
          }
        }).filter(event => event !== null);
        
        console.log("\n🎉 Events emitted:");
        events.forEach(event => {
          if (event.name === "PingReceived") {
            console.log("  📨 PingReceived:");
            console.log("    Chain ID:", event.args.sourceChainId.toString());
            console.log("    Ping ID:", event.args.pingId);
            console.log("    Original Sender:", event.args.originalSender);
            console.log("    Block Number:", event.args.originalBlockNumber.toString());
          } else if (event.name === "PingVerified") {
            console.log("  ✅ PingVerified:");
            console.log("    Ping ID:", event.args.pingId);
            console.log("    Success:", event.args.success);
            console.log("    Message:", event.args.message);
          }
        });
      } else {
        throw new Error("Transaction failed");
      }
      
    } catch (error) {
      console.error("❌ Error relaying message:", error.message);
      
      // Provide helpful debugging information
      if (error.message.includes("PingAlreadyReceived")) {
        console.log("\n💡 This ping has already been received on the destination chain.");
        console.log("   Each ping can only be relayed once to prevent replay attacks.");
      } else if (error.message.includes("InvalidEventFormat")) {
        console.log("\n💡 The proof contains invalid event data format.");
        console.log("   Ensure the proof was generated for a valid Ping event.");
      } else if (error.message.includes("InvalidProof")) {
        console.log("\n💡 Cryptographic proof verification failed.");
        console.log("   Possible causes:");
        console.log("   - Block hash not available to oracle adapters");
        console.log("   - Proof generated for wrong block/transaction");
        console.log("   - Oracle consensus not reached");
      }
      
      throw error;
    }
  });