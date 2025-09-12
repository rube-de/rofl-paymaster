import { HardhatRuntimeEnvironment } from "hardhat/types";
import * as fs from "fs";
import * as path from "path";

export interface DeploymentInfo {
  network: string;
  contractAddress: string;
  contractName: string;
  deployer: string;
  blockNumber: number;
  timestamp: string;
  transactionHash?: string;
  constructorArgs?: any[];
  [key: string]: any; // Allow additional custom fields
}

/**
 * Saves deployment information to a JSON file in the deployments directory
 * @param contractName Name of the deployed contract
 * @param contractAddress Address of the deployed contract
 * @param hre Hardhat Runtime Environment
 * @param additionalInfo Optional additional deployment metadata
 * @returns Path to the saved deployment file
 */
export async function saveDeploymentInfo(
  contractName: string,
  contractAddress: string,
  hre: HardhatRuntimeEnvironment,
  additionalInfo?: Partial<DeploymentInfo>
): Promise<string> {
  const { ethers } = hre;
  const [deployer] = await ethers.getSigners();
  
  // Prepare deployment info
  const deploymentInfo: DeploymentInfo = {
    network: hre.network.name,
    contractName,
    contractAddress,
    deployer: deployer.address,
    blockNumber: await ethers.provider.getBlockNumber(),
    timestamp: new Date().toISOString(),
    ...additionalInfo, // Merge any additional info provided
  };
  
  // Create deployments directory and network subdirectory if they don't exist
  const deploymentsDir = path.join(__dirname, "../../deployments");
  const networkDir = path.join(deploymentsDir, hre.network.name);
  
  if (!fs.existsSync(networkDir)) {
    fs.mkdirSync(networkDir, { recursive: true });
  }
  
  // Create deployment file in network-specific folder
  const deploymentFile = path.join(
    networkDir,
    `${contractName}.json`
  );
  
  // Write deployment info to file
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  
  console.log(`Deployment info saved to: ${deploymentFile}`);
  
  return deploymentFile;
}

/**
 * Loads deployment information from a saved JSON file
 * @param contractName Name of the deployed contract
 * @param networkName Network name
 * @returns Deployment info or null if not found
 */
export function loadDeploymentInfo(
  contractName: string,
  networkName: string
): DeploymentInfo | null {
  const deploymentsDir = path.join(__dirname, "../../deployments");
  const networkDir = path.join(deploymentsDir, networkName);
  const deploymentFile = path.join(networkDir, `${contractName}.json`);
  
  if (!fs.existsSync(deploymentFile)) {
    return null;
  }
  
  try {
    const data = fs.readFileSync(deploymentFile, "utf8");
    return JSON.parse(data) as DeploymentInfo;
  } catch (error) {
    console.error(`Error loading deployment info from ${deploymentFile}:`, error);
    return null;
  }
}