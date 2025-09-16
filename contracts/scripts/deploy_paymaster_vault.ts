import { ethers, upgrades } from "hardhat";
import "dotenv/config";

/*
Deploys PaymasterVault (UUPS proxy) on a remote chain.

Env vars:
- VAULT_OWNER (fallback: OWNER)
- BLOCK_HEADER_REQUESTER
*/

async function main() {
  const vaultOwner = (process.env.VAULT_OWNER || process.env.OWNER) as string;
  const blockHeaderRequester = process.env.BLOCK_HEADER_REQUESTER as string;

  if (!vaultOwner || !blockHeaderRequester) {
    throw new Error("Missing env: VAULT_OWNER/OWNER and BLOCK_HEADER_REQUESTER");
  }

  const PaymasterVault = await ethers.getContractFactory("PaymasterVault");
  const proxy = await upgrades.deployProxy(
    PaymasterVault,
    [vaultOwner, blockHeaderRequester],
    {
      kind: "uups",
      initializer: "initialize",
    }
  );

  await proxy.waitForDeployment();
  const proxyAddress = await proxy.getAddress();
  const implAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);

  const vault = await ethers.getContractAt("PaymasterVault", proxyAddress);
  const finalOwner = await vault.owner();
  const bhr = await vault.blockHeaderRequester();

  console.log("PaymasterVault deployed as UUPS proxy");
  console.log("Proxy:", proxyAddress);
  console.log("Implementation:", implAddress);
  console.log("Owner:", finalOwner);
  console.log("BlockHeaderRequester:", bhr);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

