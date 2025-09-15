# ROFL Paymaster Hardhat Workspace

## Quick Commands

- Compile: `bun hardhat compile`
- Help: `bun hardhat help`

See `.env.example` for required variables. Copy to `.env` and fill values before deployment.

## Required Dev Dependencies

- `@openzeppelin/hardhat-upgrades` for UUPS deploy/upgrade tasks

## Environment Variables

- CrossChainPaymaster: `OWNER`, `PRICE_ORACLE`, `SHOYU_BASHI`
- PaymasterVault: `PAYMASTER_VAULT_OWNER`, `BLOCK_HEADER_REQUESTER`
- Optional limits: `DAILY_LIMIT_ROSE`, `PER_TX_LIMIT_ROSE`, `LIMITS_ENABLED`
- Upgrade helpers: `PAYMASTER_SAPPHIRE_PROXY`, `PAYMASTER_VAULT_PROXY`, `RUN_VALIDATION`

## CrossChainPaymaster

### Deploy

- Task: `bun hardhat deploy:cross-chain-paymaster --network sapphireTestnet`
- Env (or flags):
  - `OWNER`, `PRICE_ORACLE`, `SHOYU_BASHI`
  - `DAILY_LIMIT_ROSE` (default 10000), `PER_TX_LIMIT_ROSE` (default 100), `LIMITS_ENABLED` (default true)
- Outputs proxy, implementation, owner

### Configure

- Task:
  `bun hardhat configure:cross-chain-paymaster \
    --proxy <paymaster> --chainid <id> \
    [--vault <vault>] [--authorize true] \
    [--daily 25000] [--pertx 250] [--limitsenabled true] \
    --network sapphireTestnet`
- Options:
  - Chain config: `--enabled`, `--confirmations`, `--blocktime`, `--maxrose`
  - Vault auth: `--vault`, `--authorize`
  - Limits: `--daily`, `--pertx`, `--limitsenabled`

### Upgrade

- Task: `bun hardhat upgrade:cross-chain-paymaster --proxy <paymaster> [--skipcheck true] --network sapphireTestnet`
- Or env: `PAYMASTER_SAPPHIRE_PROXY`, `RUN_VALIDATION`

## PaymasterVault (Remote Chain)

### Deploy

- Task: `bun hardhat deploy:paymaster-vault --network baseSepolia`
- Env (or flags): `PAYMASTER_VAULT_OWNER`, `BLOCK_HEADER_REQUESTER`

### Configure Token

- Task:
  `bun hardhat configure:paymaster-vault \
    --proxy <vault> --token <token> --decimals 6 \
    --min 10 --max 10000 --dailylimit 50000 --breakerenabled true \
    --network baseSepolia`
- Sets asset bounds and per-token circuit breaker

### Upgrade

- Task: `bun hardhat upgrade:paymaster-vault --proxy <vault> [--skipcheck true] --network baseSepolia`
- Or env: `PAYMASTER_VAULT_PROXY`, `RUN_VALIDATION`

## Scripts

- CrossChainPaymaster: `scripts/deploy_cross_chain_paymaster.ts`
- PaymasterVault: `scripts/deploy_paymaster_vault.ts`
- Run with the same env variables as the tasks
