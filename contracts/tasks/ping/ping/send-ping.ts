import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

task("send-ping", "Send a simple cross-chain ping")
  .addOptionalParam("sender", "Address of PingSender contract", "0xDCC23A03E6b6aA254cA5B0be942dD5CafC9A2299")
  .addOptionalParam("from", "Sender address (defaults to first signer)")
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;
    
    // Get signer
    const signers = await ethers.getSigners();
    const fromIndex = taskArgs.from ? 
      signers.findIndex(s => s.address.toLowerCase() === taskArgs.from.toLowerCase()) : 0;
    
    if (fromIndex === -1) {
      throw new Error(`Signer not found: ${taskArgs.from}`);
    }
    
    const signer = signers[fromIndex];
    
    console.log("🏓 Sending Simple Ping");
    console.log("Sender:", signer.address);
    console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(signer.address)), "ETH");
    console.log("PingSender contract:", taskArgs.sender);
    
    // Connect to PingSender contract
    const pingSender = await ethers.getContractAt("PingSender", taskArgs.sender, signer);
    
    // Get source chain ID
    const sourceChainId = await pingSender.SOURCE_CHAIN_ID();
    console.log("Source chain ID:", sourceChainId.toString());
    
    // Send ping transaction
    console.log("\n🏓 Sending ping...");
    try {
      const tx = await pingSender.ping();
      console.log("Transaction hash:", tx.hash);
      console.log("Waiting for confirmation...");
      
      const receipt = await tx.wait();
      
      if (!receipt) {
        throw new Error("Transaction failed - no receipt");
      }
      
      console.log("✅ Ping sent successfully!");
      console.log("Block number:", receipt.blockNumber);
      console.log("Gas used:", receipt.gasUsed.toString());
      
      // Parse events
      const pingEvent = receipt.logs.find(log => {
        try {
          return pingSender.interface.parseLog(log)?.name === "Ping";
        } catch {
          return false;
        }
      });
      
      const headerRequestedEvent = receipt.logs.find(log => {
        try {
          return pingSender.interface.parseLog(log)?.name === "HeaderRequested";
        } catch {
          return false;
        }
      });
    
      if (pingEvent) {
        const parsedEvent = pingSender.interface.parseLog(pingEvent);
        console.log("\n🎯 Ping Event Detected:");
        console.log("  Sender:", parsedEvent!.args.sender);
        console.log("  Block Number:", parsedEvent!.args.blockNumber.toString());
      }
      
      if (headerRequestedEvent) {
        const parsedEvent = pingSender.interface.parseLog(headerRequestedEvent);
        console.log("\n📋 Block Header Requested:");
        console.log("  Source Chain ID:", parsedEvent!.args.sourceChainId.toString());
        console.log("  Block Number:", parsedEvent!.args.blockNumber.toString());
        console.log("  Ping ID:", parsedEvent!.args.pingId);
      }
      
      // Generate ping ID from the transaction
      const pingId = await pingSender.generatePingId(
        sourceChainId,
        signer.address,
        receipt.blockNumber
      );
      
      // Summary for ROFL processing
      console.log("\n🔗 ROFL Processing Info:");
      console.log("  Network:", hre.network.name);
      console.log("  Chain ID:", (await ethers.provider.getNetwork()).chainId.toString());
      console.log("  Transaction Hash:", tx.hash);
      console.log("  Block Number:", receipt.blockNumber);
      console.log("  Ping ID:", pingId);
      console.log("  Sender:", signer.address);
      
      return {
        pingId,
        transactionHash: tx.hash,
        blockNumber: receipt.blockNumber,
        gasUsed: receipt.gasUsed.toString(),
        sender: signer.address
      };
    } catch (error) {
      console.error("❌ Ping failed:", error);
      throw error;
    }
  });