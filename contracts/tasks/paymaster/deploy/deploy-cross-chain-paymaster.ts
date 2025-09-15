import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

task("deploy:cross-chain-paymaster", "Deploy CrossChainPaymaster (UUPS)")
  .addOptionalParam("owner", "Owner address (falls back to env OWNER)")
  .addOptionalParam("operator", "ROFL operator address (falls back to env OPERATOR)")
  .addOptionalParam("oracle", "Price oracle address (falls back to env PRICE_ORACLE)")
  .addOptionalParam("shoyubashi", "ShoyuBashi address (falls back to env SHOYU_BASHI)")
  .addOptionalParam("daily", "Daily ROSE limit (ether units, falls back to env DAILY_LIMIT_ROSE)")
  .addOptionalParam("pertx", "Per-tx ROSE limit (ether units, falls back to env PER_TX_LIMIT_ROSE)")
  .addOptionalParam("enabled", "Limits enabled true/false (falls back to env LIMITS_ENABLED)")
  .setAction(async (args: {
    owner?: string;
    operator?: string;
    oracle?: string;
    shoyubashi?: string;
    daily?: string;
    pertx?: string;
    enabled?: string;
  }, hre: HardhatRuntimeEnvironment) => {
    const { ethers, upgrades } = hre;

    const owner = args.owner || process.env.OWNER;
    const operator = args.operator || process.env.OPERATOR;
    const oracle = args.oracle || process.env.PRICE_ORACLE;
    const shoyubashi = args.shoyubashi || process.env.SHOYUBASHI || process.env.SHOYU_BASHI;
    const daily = args.daily || process.env.DAILY_LIMIT_ROSE || "10000";
    const pertx = args.pertx || process.env.PER_TX_LIMIT_ROSE || "100";
    const enabledStr = (args.enabled || process.env.LIMITS_ENABLED || "true").toLowerCase();
    const enabled = enabledStr === "true";

    if (!owner) throw new Error("Missing owner: pass --owner or set OWNER env");
    if (!operator) throw new Error("Missing operator: pass --operator or set OPERATOR env");
    if (!oracle) throw new Error("Missing price oracle: pass --oracle or set PRICE_ORACLE env");
    if (!shoyubashi) throw new Error("Missing ShoyuBashi: pass --shoyubashi or set SHOYU_BASHI env");

    const limits = {
      dailyLimit: ethers.parseUnits(daily, 18),
      currentDaily: 0n,
      perTxLimit: ethers.parseUnits(pertx, 18),
      lastResetDay: Math.floor(Date.now() / 1000 / 86400),
      enabled,
    };

    console.log("Network:", hre.network.name);
    console.log("Owner:", owner);
    console.log("Operator:", operator);
    console.log("Oracle:", oracle);
    console.log("ShoyuBashi:", shoyubashi);
    console.log("Limits:", limits);

    const CrossChainPaymaster = await ethers.getContractFactory("CrossChainPaymaster");
    const proxy = await upgrades.deployProxy(
      CrossChainPaymaster,
      [owner, operator, oracle, shoyubashi, limits],
      { kind: "uups", initializer: "initialize" }
    );

    await proxy.waitForDeployment();
    const proxyAddress = await proxy.getAddress();
    const implAddress = await upgrades.erc1967.getImplementationAddress(proxyAddress);

    const paymaster = await ethers.getContractAt("CrossChainPaymaster", proxyAddress);
    const finalOwner = await paymaster.owner();
    const roflOperator = await paymaster.roflOperator();

    console.log("CrossChainPaymaster deployed as UUPS proxy");
    console.log("Proxy:", proxyAddress);
    console.log("Implementation:", implAddress);
    console.log("Owner:", finalOwner);
    console.log("Operator:", roflOperator);
  });

