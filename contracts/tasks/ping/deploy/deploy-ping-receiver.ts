import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";
import { saveDeploymentInfo } from "../utils/save-deployment";

task("deploy:ping-receiver", "Deploy PingReceiver contract")
  .addParam("shoyuBashi", "Address of ShoyuBashi contract")
  .setAction(async (taskArgs, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;
    const [deployer] = await ethers.getSigners();
    
    console.log("Deploying PingReceiver with the account:", deployer.address);
    console.log("Account balance:", (await ethers.provider.getBalance(deployer.address)).toString());
    
    const shoyuBashiAddress = taskArgs.shoyuBashi;
    
    console.log("ShoyuBashi address:", shoyuBashiAddress);
    
    // Verify ShoyuBashi contract exists
    try {
      const code = await ethers.provider.getCode(shoyuBashiAddress);
      if (code === "0x") {
        throw new Error("ShoyuBashi contract not found at provided address");
      }
    } catch (error) {
      console.error("Failed to verify ShoyuBashi contract:", error);
      process.exit(1);
    }
    
    // Deploy PingReceiver
    const PingReceiver = await ethers.getContractFactory("PingReceiver");
    console.log("Deploying PingReceiver...");
    
    const pingReceiver = await PingReceiver.deploy(
      shoyuBashiAddress
    );
    
    await pingReceiver.waitForDeployment();
    const pingReceiverAddress = await pingReceiver.getAddress();
    
    console.log("PingReceiver deployed to:", pingReceiverAddress);
    console.log("Constructor arguments:");
    console.log("  ShoyuBashi:", shoyuBashiAddress);
    
    // Verify deployment
    console.log("\nVerifying deployment...");
    const deployedShoyuBashi = await pingReceiver.SHOYU_BASHI();
    
    console.log("Verified ShoyuBashi:", deployedShoyuBashi);
    
    if (deployedShoyuBashi === shoyuBashiAddress) {
      console.log("✅ Deployment verified successfully!");
    } else {
      console.log("❌ Deployment verification failed!");
      process.exit(1);
    }
    
    // Save deployment info
    await saveDeploymentInfo(
      "PingReceiver",
      pingReceiverAddress,
      hre,
      {
        transactionHash: pingReceiver.deploymentTransaction()?.hash,
        constructorArgs: [shoyuBashiAddress],
        shoyuBashi: shoyuBashiAddress
      }
    );
    
    console.log("\nDeployment Summary:");
    console.log({
      network: hre.network.name,
      pingReceiver: pingReceiverAddress,
      shoyuBashi: shoyuBashiAddress,
      deployer: deployer.address
    });
    
    // Additional setup instructions
    console.log("\n📋 Next Steps:");
    console.log("1. Configure the ROFL relayer with this contract address");
    console.log("2. Verify ShoyuBashi has the required oracle adapters configured");
    console.log("3. Test with a ping event from the source chain");
    console.log("4. No authorization needed - anyone with valid proof can call receivePing()");
    
    return pingReceiverAddress;
  });