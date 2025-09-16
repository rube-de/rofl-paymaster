import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

function toBool(v?: string | boolean): boolean {
  if (typeof v === "boolean") return v;
  if (!v) return false;
  const s = v.toLowerCase();
  return s === "true" || s === "1" || s === "yes";
}

task("configure:cross-chain-paymaster", "Post-deploy configuration for CrossChainPaymaster")
  .addOptionalParam("proxy", "Deployed CrossChainPaymaster proxy address (or set env PAYMASTER_PROXY_ADDRESS)")
  .addOptionalParam("chainid", "Source chain ID to configure (or set env PAYMASTER_SOURCE_CHAIN_ID)")
  .addOptionalParam("enabled", "Enable/disable chain (default: env PAYMASTER_CHAIN_ENABLED or true)")
  .addOptionalParam("confirmations", "Required confirmations (default: env PAYMASTER_CONFIRMATIONS or 0)")
  .addOptionalParam("blocktime", "Average block time in seconds (default: env PAYMASTER_BLOCK_TIME or 2)")
  .addOptionalParam("maxrose", "Max per-tx amount in ROSE (ether units; env PAYMASTER_MAX_ROSE)")
  .addOptionalParam("vault", "Authorize this source vault for the chain (env PAYMASTER_SOURCE_VAULT)")
  .addOptionalParam("authorize", "Authorize=true / deauthorize=false (default: env PAYMASTER_AUTHORIZE_VAULT or true)")
  .addOptionalParam("daily", "Daily ROSE limit (ether units; env DAILY_LIMIT_ROSE)")
  .addOptionalParam("pertx", "Per-tx ROSE limit (ether units; env PER_TX_LIMIT_ROSE)")
  .addOptionalParam("limitsenabled", "Limits enabled true/false (env LIMITS_ENABLED)")
  .setAction(async (args: any, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    const proxy: string = args.proxy ?? process.env.PAYMASTER_PROXY_ADDRESS ?? process.env.PROXY_ADDRESS;
    if (!proxy) throw new Error("Missing proxy: pass --proxy or set PAYMASTER_PROXY_ADDRESS env");

    const chainIdEnv = process.env.PAYMASTER_SOURCE_CHAIN_ID;
    const chainId: number = args.chainid ? parseInt(args.chainid) : (chainIdEnv ? parseInt(chainIdEnv) : NaN);
    if (Number.isNaN(chainId)) throw new Error("Missing chain ID: pass --chainid or set PAYMASTER_SOURCE_CHAIN_ID env");

    const enabled: boolean = args.enabled !== undefined
      ? toBool(args.enabled)
      : (process.env.PAYMASTER_CHAIN_ENABLED !== undefined ? toBool(process.env.PAYMASTER_CHAIN_ENABLED) : true);

    const confirmations: number = args.confirmations !== undefined
      ? parseInt(args.confirmations)
      : (process.env.PAYMASTER_CONFIRMATIONS !== undefined ? parseInt(process.env.PAYMASTER_CONFIRMATIONS) : 0);

    const blockTime: number = args.blocktime !== undefined
      ? parseInt(args.blocktime)
      : (process.env.PAYMASTER_BLOCK_TIME !== undefined ? parseInt(process.env.PAYMASTER_BLOCK_TIME) : 2);

    const maxRoseStr: string | undefined = args.maxrose ?? process.env.PAYMASTER_MAX_ROSE;
    const vault: string | undefined = args.vault ?? process.env.VAULT_PROXY_ADDRESS
    const authorize: boolean = args.authorize !== undefined
      ? toBool(args.authorize)
      : (process.env.PAYMASTER_AUTHORIZE_VAULT !== undefined ? toBool(process.env.PAYMASTER_AUTHORIZE_VAULT) : true);

    const dailyStr: string | undefined = args.daily ?? process.env.DAILY_LIMIT_ROSE;
    const perTxStr: string | undefined = args.pertx ?? process.env.PER_TX_LIMIT_ROSE;
    const limitsEnabled: boolean | undefined = args.limitsenabled !== undefined
      ? toBool(args.limitsenabled)
      : (process.env.LIMITS_ENABLED !== undefined ? toBool(process.env.LIMITS_ENABLED) : undefined);

    const paymaster = await ethers.getContractAt("CrossChainPaymaster", proxy);

    console.log("Network:", hre.network.name);
    console.log("Proxy:", proxy);

    // 1) Set chain config if any config param provided either via CLI or env
    const hasChainCfgArg = args.enabled !== undefined || args.confirmations !== undefined || args.blocktime !== undefined || args.maxrose !== undefined;
    const hasChainCfgEnv = process.env.PAYMASTER_CHAIN_ENABLED !== undefined || process.env.PAYMASTER_CONFIRMATIONS !== undefined || process.env.PAYMASTER_BLOCK_TIME !== undefined || process.env.PAYMASTER_MAX_ROSE !== undefined;
    if (hasChainCfgArg || hasChainCfgEnv) {
      const maxAmount = maxRoseStr ? ethers.parseUnits(maxRoseStr, 18) : 0n;
      const cfg = {
        chainId,
        enabled,
        confirmations,
        blockTime,
        maxAmount,
      };
      console.log("Setting chain config:", cfg);
      const tx = await paymaster.setChainConfig(chainId, cfg);
      console.log("tx:", tx.hash);
      await tx.wait();
    }

    // 2) Authorize/deauthorize source vault if provided
    if (vault) {
      console.log(`${authorize ? "Authorizing" : "Deauthorizing"} vault ${vault} for chain ${chainId}`);
      const tx = await paymaster.setVaultAuthorization(chainId, vault, authorize);
      console.log("tx:", tx.hash);
      await tx.wait();
    }

    // 3) Update distribution limits if provided via CLI or env
    if (dailyStr || perTxStr || limitsEnabled !== undefined) {
      const current = await paymaster.limits();
      const daily = dailyStr ? ethers.parseUnits(dailyStr, 18) : current.dailyLimit;
      const perTx = perTxStr ? ethers.parseUnits(perTxStr, 18) : current.perTxLimit;
      const enabledLimits = limitsEnabled !== undefined ? limitsEnabled : current.enabled;
      console.log("Updating distribution limits:", {
        dailyLimit: daily.toString(),
        perTxLimit: perTx.toString(),
        enabled: enabledLimits,
      });
      const tx = await paymaster.setDistributionLimits(daily, perTx, enabledLimits);
      console.log("tx:", tx.hash);
      await tx.wait();
    }

    console.log("✅ CrossChainPaymaster configuration completed");
  });
