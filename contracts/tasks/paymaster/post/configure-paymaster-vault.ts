import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

function toBool(v?: string | boolean): boolean {
  if (typeof v === "boolean") return v;
  if (!v) return false;
  const s = v.toLowerCase();
  return s === "true" || s === "1" || s === "yes";
}

task("configure:paymaster-vault", "Post-deploy configuration for PaymasterVault")
  .addParam("proxy", "Deployed PaymasterVault proxy address")
  .addOptionalParam("token", "ERC20 token address to configure")
  .addOptionalParam("enabled", "Enable/disable deposits for token (default: true)")
  .addOptionalParam("decimals", "Token decimals (0-18; required if setting min/max)")
  .addOptionalParam("min", "Minimum deposit amount (whole tokens, parsed with 'decimals')")
  .addOptionalParam("max", "Maximum deposit amount (whole tokens, parsed with 'decimals')")
  .addOptionalParam("dailylimit", "Per-token daily limit (whole tokens, parsed with 'decimals')")
  .addOptionalParam("breakerenabled", "Enable per-token circuit breaker (default: true)")
  .setAction(async (args: any, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    const proxy: string = args.proxy;
    const token: string | undefined = args.token;
    const enabled: boolean = args.enabled !== undefined ? toBool(args.enabled) : true;
    const decimals: number | undefined = args.decimals ? parseInt(args.decimals) : undefined;
    const minStr: string | undefined = args.min;
    const maxStr: string | undefined = args.max;
    const dailyStr: string | undefined = args.dailylimit;
    const breakerEnabled: boolean = args.breakerenabled !== undefined ? toBool(args.breakerenabled) : true;

    const vault = await ethers.getContractAt("PaymasterVault", proxy);

    console.log("Network:", hre.network.name);
    console.log("Proxy:", proxy);

    // 1) Configure token asset if provided
    if (token) {
      if (decimals === undefined) {
        throw new Error("--decimals is required when configuring token min/max amounts");
      }
      if (decimals < 0 || decimals > 18) throw new Error("decimals must be between 0 and 18");

      const minAmount = minStr ? ethers.parseUnits(minStr, decimals) : 0n;
      const maxAmount = maxStr ? ethers.parseUnits(maxStr, decimals) : 0n;

      const cfg = {
        enabled,
        decimals,
        minAmount,
        maxAmount,
      };
      console.log("Setting token config:", token, cfg);
      const tx = await vault.setTokenConfig(token, cfg);
      console.log("tx:", tx.hash);
      await tx.wait();

      // 2) Circuit breaker settings for token
      if (dailyStr) {
        const daily = ethers.parseUnits(dailyStr, decimals);
        console.log("Setting per-token daily limit:", daily.toString());
        const ltx = await vault.setTokenDailyLimit(token, daily);
        console.log("tx:", ltx.hash);
        await ltx.wait();
      }
      if (args.breakerenabled !== undefined) {
        console.log("Setting per-token circuit breaker enabled:", breakerEnabled);
        const etx = await vault.setTokenCircuitBreakerEnabled(token, breakerEnabled);
        console.log("tx:", etx.hash);
        await etx.wait();
      }
    }

    console.log("✅ PaymasterVault configuration completed");
  });

