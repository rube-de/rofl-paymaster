import { ethers, upgrades } from "hardhat";
import "@openzeppelin/hardhat-upgrades";

/*
Upgrades an existing CrossChainPaymaster UUPS proxy to a new implementation.

Required env vars:
- PROXY_ADDRESS

Optional validation:
- RUN_VALIDATION ("true" | "false", default: "true")
*/

async function main() {
  const proxyAddress = process.env.PROXY_ADDRESS as string;
  if (!proxyAddress) throw new Error("Missing env: PROXY_ADDRESS");

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

