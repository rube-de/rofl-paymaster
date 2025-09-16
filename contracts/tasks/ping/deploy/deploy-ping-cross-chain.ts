import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";
import "hardhat-switch-network";
import { saveDeploymentInfo } from "../utils/save-deployment";

task("deploy:ping-cross-chain", "Deploy ping system across source and target chains")
  .addOptionalParam("sourceNetwork", "Source network for PingSender", "eth-sepolia")
  .addOptionalParam("targetNetwork", "Target network for PingReceiver", "sapphire-testnet")
  .addParam("shoyuBashi", "Address of ShoyuBashi contract on target chain")
  .addOptionalParam("blockHeaderRequester", "Address of existing BlockHeaderRequester on source chain")
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    console.log("🚀 Deploying Cross-Chain Ping System");
    console.log("Source network:", taskArgs.sourceNetwork);
    console.log("Target network:", taskArgs.targetNetwork);
    console.log("");
    
    // Store deployment results
    let blockHeaderRequesterAddress = taskArgs.blockHeaderRequester;
    let pingSenderAddress: string;
    let pingReceiverAddress: string;
    let sourceChainId: bigint;
    let targetChainId: bigint;
    
    // Step 1: Deploy on source network (PingSender + BlockHeaderRequester)
    console.log(`📡 Switching to source network: ${taskArgs.sourceNetwork}`);
    await hre.switchNetwork(taskArgs.sourceNetwork);
    
    const { ethers: sourceEthers } = hre;
    const [sourceDeployer] = await sourceEthers.getSigners();
    const sourceNetwork = await sourceEthers.provider.getNetwork();
    sourceChainId = sourceNetwork.chainId;
    
    console.log("Source network details:");
    console.log("  Network:", hre.network.name);
    console.log("  Chain ID:", sourceChainId.toString());
    console.log("  Deployer:", sourceDeployer.address);
    console.log("  Balance:", sourceEthers.formatEther(await sourceEthers.provider.getBalance(sourceDeployer.address)), "ETH");
    console.log("");
    
    // Deploy or verify BlockHeaderRequester on source chain
    if (!blockHeaderRequesterAddress) {
      console.log("📦 Deploying BlockHeaderRequester on source chain...");
      const BlockHeaderRequester = await sourceEthers.getContractFactory("BlockHeaderRequester");
      const blockHeaderRequester = await BlockHeaderRequester.deploy();
      await blockHeaderRequester.waitForDeployment();
      blockHeaderRequesterAddress = await blockHeaderRequester.getAddress();
      console.log("  BlockHeaderRequester deployed to:", blockHeaderRequesterAddress);
      
      // Save BlockHeaderRequester deployment
      await saveDeploymentInfo(
        "BlockHeaderRequester",
        blockHeaderRequesterAddress,
        hre,
        {
          transactionHash: blockHeaderRequester.deploymentTransaction()?.hash,
          constructorArgs: []
        }
      );
    } else {
      console.log("Using existing BlockHeaderRequester:", blockHeaderRequesterAddress);
      const code = await sourceEthers.provider.getCode(blockHeaderRequesterAddress);
      if (code === "0x") {
        throw new Error("BlockHeaderRequester not found at provided address on source chain");
      }
      console.log("  ✅ BlockHeaderRequester verified");
    }
    
    // Deploy PingSender on source chain
    console.log("📦 Deploying PingSender on source chain...");
    const PingSender = await sourceEthers.getContractFactory("PingSender");
    const pingSender = await PingSender.deploy(
      blockHeaderRequesterAddress,
      sourceChainId
    );
    await pingSender.waitForDeployment();
    pingSenderAddress = await pingSender.getAddress();
    console.log("  PingSender deployed to:", pingSenderAddress);
    
    // Save PingSender deployment
    await saveDeploymentInfo(
      "PingSender",
      pingSenderAddress,
      hre,
      {
        transactionHash: pingSender.deploymentTransaction()?.hash,
        constructorArgs: [blockHeaderRequesterAddress, sourceChainId.toString()],
        blockHeaderRequester: blockHeaderRequesterAddress,
        sourceChainId: sourceChainId.toString()
      }
    );
    
    // Verify PingSender deployment
    const deployedBlockHeaderRequester = await pingSender.blockHeaderRequester();
    const deployedSourceChainId = await pingSender.SOURCE_CHAIN_ID();
    console.log("  Verification:");
    console.log("    BlockHeaderRequester:", deployedBlockHeaderRequester === blockHeaderRequesterAddress ? "✅" : "❌");
    console.log("    Source Chain ID:", deployedSourceChainId.toString() === sourceChainId.toString() ? "✅" : "❌");
    console.log("");
    
    // Step 2: Deploy on target network (PingReceiver)
    console.log(`📡 Switching to target network: ${taskArgs.targetNetwork}`);
    await hre.switchNetwork(taskArgs.targetNetwork);
    
    const { ethers: targetEthers } = hre;
    const [targetDeployer] = await targetEthers.getSigners();
    const targetNetwork = await targetEthers.provider.getNetwork();
    targetChainId = targetNetwork.chainId;
    
    console.log("Target network details:");
    console.log("  Network:", hre.network.name);
    console.log("  Chain ID:", targetChainId.toString());
    console.log("  Deployer:", targetDeployer.address);
    console.log("  Balance:", targetEthers.formatEther(await targetEthers.provider.getBalance(targetDeployer.address)), "ETH");
    console.log("");
    
    // Verify ShoyuBashi exists on target chain
    console.log("Verifying ShoyuBashi on target chain...");
    const shoyuBashiCode = await targetEthers.provider.getCode(taskArgs.shoyuBashi);
    if (shoyuBashiCode === "0x") {
      console.error("❌ ShoyuBashi contract not found at", taskArgs.shoyuBashi, "on target chain");
      console.error("   Please deploy ShoyuBashi first or provide correct address");
      throw new Error("ShoyuBashi not found on target chain");
    }
    console.log("  ✅ ShoyuBashi verified at:", taskArgs.shoyuBashi);
    
    // Deploy PingReceiver on target chain
    console.log("📦 Deploying PingReceiver on target chain...");
    const PingReceiver = await targetEthers.getContractFactory("PingReceiver");
    const pingReceiver = await PingReceiver.deploy(taskArgs.shoyuBashi);
    await pingReceiver.waitForDeployment();
    pingReceiverAddress = await pingReceiver.getAddress();
    console.log("  PingReceiver deployed to:", pingReceiverAddress);
    
    // Save PingReceiver deployment
    await saveDeploymentInfo(
      "PingReceiver",
      pingReceiverAddress,
      hre,
      {
        transactionHash: pingReceiver.deploymentTransaction()?.hash,
        constructorArgs: [taskArgs.shoyuBashi],
        shoyuBashi: taskArgs.shoyuBashi
      }
    );
    
    // Verify PingReceiver deployment
    const deployedShoyuBashi = await pingReceiver.SHOYU_BASHI();
    console.log("  Verification:");
    console.log("    ShoyuBashi:", deployedShoyuBashi === taskArgs.shoyuBashi ? "✅" : "❌");
    console.log("");
    
    // Step 3: Generate deployment summary
    const deploymentSummary = {
      sourceNetwork: {
        name: taskArgs.sourceNetwork,
        chainId: sourceChainId.toString(),
        contracts: {
          blockHeaderRequester: blockHeaderRequesterAddress,
          pingSender: pingSenderAddress
        }
      },
      targetNetwork: {
        name: taskArgs.targetNetwork,
        chainId: targetChainId.toString(),
        contracts: {
          shoyuBashi: taskArgs.shoyuBashi,
          pingReceiver: pingReceiverAddress
        }
      },
      deployer: sourceDeployer.address,
      timestamp: new Date().toISOString()
    };
    
    console.log("=" .repeat(60));
    console.log("📋 DEPLOYMENT SUMMARY");
    console.log("=" .repeat(60));
    console.log(JSON.stringify(deploymentSummary, null, 2));
    console.log("=" .repeat(60));
    
    // Step 4: Usage instructions
    console.log("\n🎯 USAGE INSTRUCTIONS");
    console.log("-".repeat(60));
    
    console.log("\n1️⃣  Send a ping from source chain:");
    console.log(`   npx hardhat send-ping --network ${taskArgs.sourceNetwork} \\`);
    console.log(`     --sender ${pingSenderAddress}`);
    
    console.log("\n2️⃣  Check ping status on target chain:");
    console.log(`   npx hardhat check-ping --network ${taskArgs.targetNetwork} \\`);
    console.log(`     --receiver ${pingReceiverAddress} \\`);
    console.log(`     --ping-id <ping-id-from-send>`);
    
    console.log("\n3️⃣  ROFL Relayer Configuration:");
    console.log("   Add these to your ROFL relayer config:");
    console.log(`   SOURCE_CHAIN_ID=${sourceChainId}`);
    console.log(`   SOURCE_PING_SENDER=${pingSenderAddress}`);
    console.log(`   TARGET_CHAIN_ID=${targetChainId}`);
    console.log(`   TARGET_PING_RECEIVER=${pingReceiverAddress}`);
    console.log(`   BLOCK_HEADER_REQUESTER=${blockHeaderRequesterAddress}`);
    
    console.log("\n⚠️  IMPORTANT NOTES:");
    console.log("-".repeat(60));
    console.log("• Ensure ROFL application is registered and funded");
    console.log("• Configure ROFL relayer to monitor Ping events on source chain");
    console.log("• Verify ShoyuBashi has required oracle adapters on target chain");
    console.log("• No authorization needed - anyone with valid proof can execute");
    console.log("• Typical cross-chain message time: 5-10 minutes");
    
    console.log("\n✅ Cross-chain ping system deployed successfully!");
    
    return {
      source: {
        network: taskArgs.sourceNetwork,
        chainId: sourceChainId.toString(),
        blockHeaderRequester: blockHeaderRequesterAddress,
        pingSender: pingSenderAddress
      },
      target: {
        network: taskArgs.targetNetwork,
        chainId: targetChainId.toString(),
        shoyuBashi: taskArgs.shoyuBashi,
        pingReceiver: pingReceiverAddress
      }
    };
  });