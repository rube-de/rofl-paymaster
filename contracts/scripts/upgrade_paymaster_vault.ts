import { ethers, upgrades } from "hardhat";
import "dotenv/config";

/*
Upgrades an existing PaymasterVault UUPS proxy.

Env vars:
- PAYMASTER_VAULT_PROXY
- RUN_VALIDATION ("true" | "false", default: "true")
*/

async function main() {
  const proxyAddress = process.env.PAYMASTER_VAULT_PROXY as string;
  if (!proxyAddress) throw new Error("Missing env: PAYMASTER_VAULT_PROXY");

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
