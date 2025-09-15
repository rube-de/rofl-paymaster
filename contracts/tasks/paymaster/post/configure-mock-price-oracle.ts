import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

/**
 * Utilities
 */
function requireAddress(name: string, val?: string): string {
  if (!val || !/^0x[a-fA-F0-9]{40}$/.test(val)) {
    throw new Error(`Missing or invalid ${name}: got ${val ?? "<undefined>"}`);
  }
  return val;
}

// Add a token feed to MockROFLPriceOracle (or any IROFLPriceOracle-compatible impl)
// Usage:
// bunx hardhat oracle:addtokenfeed \
//   --network sapphire-testnet \
//   [--token 0xToken...] \
//   [--decimals 6] [--price 1] [--oracle 0xOracle...]
// Defaults: oracle from env PRICE_ORACLE, token from env PAYMASTER_VAULT_TOKEN, price=1 (1 ROSE), decimals from env PAYMASTER_VAULT_TOKEN_DECIMALS (else 18)
task("oracle:addtokenfeed", "Add a token feed to MockROFLPriceOracle")
  .addOptionalParam("oracle", "Oracle contract address (defaults to env PRICE_ORACLE)")
  .addOptionalParam("token", "Token address to register (defaults to env PAYMASTER_VAULT_TOKEN)")
  .addOptionalParam("price", "Initial price in ROSE units (ether units)", "1")
  .addOptionalParam("decimals", "Token decimals (0-18; default env PAYMASTER_VAULT_TOKEN_DECIMALS or 18)")
  .setAction(async (args: { oracle?: string; token: string; price?: string; decimals?: string }, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    const oracleAddr = requireAddress("oracle", args.oracle ?? process.env.PRICE_ORACLE);
    const token = requireAddress("token", args.token ?? process.env.PAYMASTER_VAULT_TOKEN);
    const decimalsStr = args.decimals ?? process.env.PAYMASTER_VAULT_TOKEN_DECIMALS ?? "18";
    const decimalsNum = parseInt(decimalsStr, 10);
    if (Number.isNaN(decimalsNum) || decimalsNum < 0 || decimalsNum > 18) {
      throw new Error(`decimals must be an integer between 0 and 18, got ${decimalsStr}`);
    }
    const priceWei = ethers.parseUnits(args.price ?? "1", 18);

    console.log("Network:", hre.network.name);
    console.log("Oracle:", oracleAddr);
    console.log("Adding token feed:", { token, price: priceWei.toString(), decimals: decimalsNum });

    const oracle = await ethers.getContractAt("IROFLPriceOracle", oracleAddr);
    const tx = await oracle.addTokenFeed(token, priceWei, decimalsNum);
    console.log("tx:", tx.hash);
    await tx.wait();
    console.log("✅ Token feed added");
  });

// Remove a token feed from MockROFLPriceOracle
// Usage:
// bunx hardhat oracle:removetokenfeed \
//   --network sapphire-testnet \
//   [--token 0xToken...] \
//   [--oracle 0xOracle...]
task("oracle:removetokenfeed", "Remove a token feed from MockROFLPriceOracle")
  .addOptionalParam("oracle", "Oracle contract address (defaults to env PRICE_ORACLE)")
  .addOptionalParam("token", "Token address to remove (defaults to env PAYMASTER_VAULT_TOKEN)")
  .setAction(async (args: { oracle?: string; token: string }, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    const oracleAddr = requireAddress("oracle", args.oracle ?? process.env.PRICE_ORACLE);
    const token = requireAddress("token", args.token ?? process.env.PAYMASTER_VAULT_TOKEN);

    console.log("Network:", hre.network.name);
    console.log("Oracle:", oracleAddr);
    console.log("Removing token feed:", { token });

    const oracle = await ethers.getContractAt("IROFLPriceOracle", oracleAddr);
    const tx = await oracle.removeTokenFeed(token);
    console.log("tx:", tx.hash);
    await tx.wait();
    console.log("✅ Token feed removed");
  });
