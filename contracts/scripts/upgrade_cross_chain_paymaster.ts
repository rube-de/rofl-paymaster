import { ethers, upgrades } from "hardhat";
import "@openzeppelin/hardhat-upgrades";

/*
Upgrades an existing CrossChainPaymaster UUPS proxy to a new implementation.

Required env vars:
- PAYMASTER_SAPPHIRE_PROXY

Optional validation:
- RUN_VALIDATION ("true" | "false", default: "true")
*/

async function main() {
  const proxyAddress = process.env.PAYMASTER_SAPPHIRE_PROXY as string;
  if (!proxyAddress) throw new Error("Missing env: PAYMASTER_SAPPHIRE_PROXY");

  const CrossChainPaymaster = await ethers.getContractFactory("CrossChainPaymaster");
  const runValidation = (process.env.RUN_VALIDATION ?? "true").toLowerCase() === "true";

  const upgraded = await upgrades.upgradeProxy(proxyAddress, CrossChainPaymaster, {
    kind: "uups",
    unsafeSkipStorageCheck: !runValidation,
  });
  await upgraded.waitForDeployment();

  const newImpl = await upgrades.erc1967.getImplementationAddress(proxyAddress);
  console.log("Upgraded CrossChainPaymaster proxy:", proxyAddress);
  console.log("New implementation:", newImpl);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
