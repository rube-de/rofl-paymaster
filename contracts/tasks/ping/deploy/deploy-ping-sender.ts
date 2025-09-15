import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";
import { saveDeploymentInfo } from "../utils/save-deployment";

task("deploy:ping-sender", "Deploy PingSender contract")
  .addParam("blockHeaderRequester", "Address of BlockHeaderRequester contract")
  .addOptionalParam("sourceChainId", "Source chain ID (defaults to network chain ID)")
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;
    const [deployer] = await ethers.getSigners();
    
    console.log("Deploying PingSender with the account:", deployer.address);
    console.log("Account balance:", (await ethers.provider.getBalance(deployer.address)).toString());
    
    const blockHeaderRequesterAddress = taskArgs.blockHeaderRequester;
    const sourceChainId = taskArgs.sourceChainId || (await ethers.provider.getNetwork()).chainId;
    
    console.log("BlockHeaderRequester address:", blockHeaderRequesterAddress);
    console.log("Source chain ID:", sourceChainId);
    
    // Verify BlockHeaderRequester contract exists
    try {
      const code = await ethers.provider.getCode(blockHeaderRequesterAddress);
      if (code === "0x") {
        throw new Error("BlockHeaderRequester contract not found at provided address");
      }
    } catch (error) {
      console.error("Failed to verify BlockHeaderRequester contract:", error);
      process.exit(1);
    }
    
    // Deploy PingSender
    const PingSender = await ethers.getContractFactory("PingSender");
    console.log("Deploying PingSender...");
    
    const pingSender = await PingSender.deploy(
      blockHeaderRequesterAddress,
      sourceChainId
    );
    
    await pingSender.waitForDeployment();
    const pingSenderAddress = await pingSender.getAddress();
    
    console.log("PingSender deployed to:", pingSenderAddress);
    console.log("Constructor arguments:");
    console.log("  BlockHeaderRequester:", blockHeaderRequesterAddress);
    console.log("  Source Chain ID:", sourceChainId);
    
    // Verify deployment
    console.log("\nVerifying deployment...");
    const deployedBlockHeaderRequester = await pingSender.blockHeaderRequester();
    const deployedSourceChainId = await pingSender.SOURCE_CHAIN_ID();
    
    console.log("Verified BlockHeaderRequester:", deployedBlockHeaderRequester);
    console.log("Verified Source Chain ID:", deployedSourceChainId.toString());
    
    if (deployedBlockHeaderRequester === blockHeaderRequesterAddress && 
        deployedSourceChainId.toString() === sourceChainId.toString()) {
      console.log("✅ Deployment verified successfully!");
    } else {
      console.log("❌ Deployment verification failed!");
      process.exit(1);
    }
    
    // Save deployment info
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
    
    console.log("\nDeployment Summary:");
    console.log({
      network: hre.network.name,
      pingSender: pingSenderAddress,
      blockHeaderRequester: blockHeaderRequesterAddress,
      sourceChainId: sourceChainId.toString(),
      deployer: deployer.address
    });
    
    return pingSenderAddress;
  });