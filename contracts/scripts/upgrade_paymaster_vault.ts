import { ethers, upgrades } from "hardhat";
import "dotenv/config";

/*
Upgrades an existing PaymasterVault UUPS proxy.

Env vars:
- VAULT_PROXY_ADDRESS (fallback: PROXY_ADDRESS)
- RUN_VALIDATION ("true" | "false", default: "true")
*/

async function main() {
  const proxyAddress = (process.env.VAULT_PROXY_ADDRESS || process.env.PROXY_ADDRESS) as string;
  if (!proxyAddress) throw new Error("Missing env: VAULT_PROXY_ADDRESS or PROXY_ADDRESS");

  const PaymasterVault = await ethers.getContractFactory("PaymasterVault");
  const runValidation = (process.env.RUN_VALIDATION ?? "true").toLowerCase() === "true";

  const upgraded = await upgrades.upgradeProxy(proxyAddress, PaymasterVault, {
    kind: "uups",
    unsafeSkipStorageCheck: !runValidation,
  });
  await upgraded.waitForDeployment();

  const newImpl = await upgrades.erc1967.getImplementationAddress(proxyAddress);
  console.log("Upgraded PaymasterVault proxy:", proxyAddress);
  console.log("New implementation:", newImpl);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

