import { ethers, upgrades } from "hardhat";
import "dotenv/config";

async function main() {
  const owner = process.env.OWNER as string;
  const priceOracle = process.env.PRICE_ORACLE as string;
  const shoyuBashi = process.env.SHOYU_BASHI as string;

  if (!owner || !priceOracle || !shoyuBashi) {
    throw new Error("Missing env: OWNER, PRICE_ORACLE, SHOYU_BASHI");
  }

  const dailyLimitRose = process.env.DAILY_LIMIT_ROSE ?? "10000";
  const perTxLimitRose = process.env.PER_TX_LIMIT_ROSE ?? "100";
  const limitsEnabled = (process.env.LIMITS_ENABLED ?? "true").toLowerCase() === "true";

  const dailyLimit = ethers.parseUnits(dailyLimitRose, 18); // uint128
  const perTxLimit = ethers.parseUnits(perTxLimitRose, 18); // uint64 fits typical ranges
  const lastResetDay = Math.floor(Date.now() / 1000 / 86400); // uint32

  const limits = {
    dailyLimit,
    currentDaily: 0n,
    perTxLimit,
    lastResetDay,
    enabled: limitsEnabled,
  };

  const CrossChainPaymaster = await ethers.getContractFactory("CrossChainPaymaster");
  const proxy = await upgrades.deployProxy(
    CrossChainPaymaster,
    [owner, priceOracle, shoyuBashi, limits],
    {
      kind: "uups",
      initializer: "initialize",
    }
  );

  await proxy.waitForDeployment();
  const proxyAddress = await proxy.getAddress();
  const implAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);
  const paymaster = await ethers.getContractAt("CrossChainPaymaster", proxyAddress);
  const finalOwner = await paymaster.owner();

  console.log("CrossChainPaymaster deployed as UUPS proxy");
  console.log("Proxy:", proxyAddress);
  console.log("Implementation:", implAddress);
  console.log("Owner:", finalOwner);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
