import { task, types } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

task("check-ping", "Check the status of a cross-chain ping")
  .addParam("receiver", "Address of PingReceiver contract")
  .addParam("pingId", "Ping ID to check")
  .addOptionalParam("detailed", "Show detailed information", false, types.boolean)
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;
    
    console.log("🔍 Checking Ping Status");
    console.log("PingReceiver contract:", taskArgs.receiver);
    console.log("Ping ID:", taskArgs.pingId);
    console.log("Network:", hre.network.name);
    console.log("Chain ID:", (await ethers.provider.getNetwork()).chainId.toString());
    
    // Connect to PingReceiver contract
    const pingReceiver = await ethers.getContractAt("PingReceiver", taskArgs.receiver);
    
    let received = false;
    let originalSender = "";
    let originalBlockNumber = 0n;
    
    try {
      // Get ping status
      [received, originalSender, originalBlockNumber] = await pingReceiver.getPingStatus(taskArgs.pingId);
      
      console.log("\n🏓 Ping Status:");
      console.log("  Received:", received ? "✅ Yes" : "❌ No");
      
      if (received) {
        console.log("  Original sender:", originalSender);
        console.log("  Original block number:", originalBlockNumber.toString());
        console.log("  Status: ✅ Ping successfully received and verified");
      } else {
        console.log("  Status: ⏳ Ping not yet received");
        console.log("");
        console.log("💡 Possible reasons:");
        console.log("  1. ROFL relayer hasn't detected the source Ping event yet");
        console.log("  2. Block header not yet available on target chain");
        console.log("  3. ROFL relayer is generating/submitting Merkle proof");
        console.log("  4. Ping is still in processing queue");
        console.log("  5. Invalid ping ID provided");
      }
      
      // If detailed, show additional contract info
      if (taskArgs.detailed) {
        console.log("\n🔧 Contract Configuration:");
        
        try {
          const shoyuBashi = await pingReceiver.SHOYU_BASHI();
          
          console.log("  ShoyuBashi address:", shoyuBashi);
          
          // Check if ShoyuBashi contract exists
          const shoyuBashiCode = await ethers.provider.getCode(shoyuBashi);
          console.log("  ShoyuBashi deployed:", shoyuBashiCode !== "0x" ? "✅" : "❌");
          
        } catch (error) {
          console.log("  Error reading contract config:", error);
        }
      }
      
      // Look for recent events related to this ping
      console.log("\n🔍 Checking Recent Events...");
      
      try {
        // Get recent PingReceived events
        const currentBlock = await ethers.provider.getBlockNumber();
        const fromBlock = Math.max(0, currentBlock - 1000); // Look back 1000 blocks
        
        const pingReceivedFilter = pingReceiver.filters.PingReceived(undefined, taskArgs.pingId);
        const pingReceivedEvents = await pingReceiver.queryFilter(pingReceivedFilter, fromBlock);
        
        const pingVerifiedFilter = pingReceiver.filters.PingVerified(taskArgs.pingId);
        const pingVerifiedEvents = await pingReceiver.queryFilter(pingVerifiedFilter, fromBlock);
        
        if (pingReceivedEvents.length > 0) {
          console.log("  🏓 PingReceived events found:", pingReceivedEvents.length);
          pingReceivedEvents.forEach((event, index) => {
            console.log(`    Event ${index + 1}:`);
            console.log(`      Block: ${event.blockNumber}`);
            console.log(`      Source Chain: ${event.args.sourceChainId}`);
            console.log(`      Original Sender: ${event.args.originalSender}`);
            console.log(`      Original Block: ${event.args.originalBlockNumber}`);
          });
        } else {
          console.log("  🏓 No PingReceived events found for this ping");
        }
        
        if (pingVerifiedEvents.length > 0) {
          console.log("  ✅ PingVerified events found:", pingVerifiedEvents.length);
          pingVerifiedEvents.forEach((event, index) => {
            console.log(`    Event ${index + 1}:`);
            console.log(`      Block: ${event.blockNumber}`);
            console.log(`      Success: ${event.args.success}`);
            console.log(`      Reason: ${event.args.reason}`);
          });
        } else {
          console.log("  ✅ No PingVerified events found for this ping");
        }
        
      } catch (error) {
        console.log("  Error querying events:", error);
      }
      
    } catch (error) {
      console.error("❌ Error checking ping status:", error);
      throw error;
    }
    
    // Helpful next steps
    if (!received) {
      console.log("\n📝 Troubleshooting Steps:");
      console.log("1. Verify the source ping transaction was successful");
      console.log("2. Check ROFL relayer logs for error messages");
      console.log("3. Confirm block headers are being submitted to target chain");
      console.log("4. Verify ROFL app has sufficient funds and authorization");
      console.log("5. Check network connectivity between chains");
      console.log("6. Verify ping ID matches the one from source transaction");
      
      console.log("\n⏱️  Typical Processing Time:");
      console.log("  - Event detection: 30-60 seconds");
      console.log("  - Header availability: 2-5 minutes");
      console.log("  - Proof generation: 1-2 minutes");
      console.log("  - Target submission: 1-2 minutes");
      console.log("  - Total expected: 5-10 minutes");
      
      console.log("\n🔧 Debug Commands:");
      console.log("  Check source ping:");
      console.log(`    npx hardhat send-ping --sender <sender-contract-address>`);
      console.log("  Generate ping ID manually:");
      console.log(`    keccak256(abi.encode(sourceChainId, senderAddress, blockNumber))`);
    }
    
    return {
      received,
      originalSender: received ? originalSender : null,
      originalBlockNumber: received ? originalBlockNumber.toString() : null
    };
  });