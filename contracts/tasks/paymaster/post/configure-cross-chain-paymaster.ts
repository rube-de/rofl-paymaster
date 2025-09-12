import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

function toBool(v?: string | boolean): boolean {
  if (typeof v === "boolean") return v;
  if (!v) return false;
  const s = v.toLowerCase();
  return s === "true" || s === "1" || s === "yes";
}

task("configure:cross-chain-paymaster", "Post-deploy configuration for CrossChainPaymaster")
  .addParam("proxy", "Deployed CrossChainPaymaster proxy address")
  .addParam("chainid", "Source chain ID to configure")
  .addOptionalParam("enabled", "Enable/disable chain (default: true)")
  .addOptionalParam("confirmations", "Required confirmations (default: 0)")
  .addOptionalParam("blocktime", "Average block time in seconds (default: 2)")
  .addOptionalParam("maxrose", "Max per-tx amount in ROSE (ether units; optional)")
  .addOptionalParam("vault", "Authorize this source vault for the chain (optional)")
  .addOptionalParam("authorize", "Authorize=true / deauthorize=false (default: true)")
  .addOptionalParam("daily", "Daily ROSE limit (ether units; optional)")
  .addOptionalParam("pertx", "Per-tx ROSE limit (ether units; optional)")
  .addOptionalParam("limitsenabled", "Limits enabled true/false (optional)")
  .setAction(async (args: any, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    const proxy: string = args.proxy;
    const chainId: number = parseInt(args.chainid);
    const enabled: boolean = args.enabled !== undefined ? toBool(args.enabled) : true;
    const confirmations: number = args.confirmations ? parseInt(args.confirmations) : 0;
    const blockTime: number = args.blocktime ? parseInt(args.blocktime) : 2;
    const maxRoseStr: string | undefined = args.maxrose;
    const vault: string | undefined = args.vault;
    const authorize: boolean = args.authorize !== undefined ? toBool(args.authorize) : true;
    const dailyStr: string | undefined = args.daily;
    const perTxStr: string | undefined = args.pertx;
    const limitsEnabled: boolean | undefined = args.limitsenabled !== undefined ? toBool(args.limitsenabled) : undefined;

    const paymaster = await ethers.getContractAt("CrossChainPaymaster", proxy);

    console.log("Network:", hre.network.name);
    console.log("Proxy:", proxy);

    // 1) Set chain config if any config param provided
    if (args.enabled !== undefined || args.confirmations !== undefined || args.blocktime !== undefined || args.maxrose !== undefined) {
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

    // 3) Update distribution limits if provided
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
      const tx = await paymaster.setDistributionLimits(daily, Number(perTx), enabledLimits);
      console.log("tx:", tx.hash);
      await tx.wait();
    }

    console.log("✅ CrossChainPaymaster configuration completed");
  });

