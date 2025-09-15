// Ping deployment tasks (optional deps) - load defensively
try { require("./ping/deploy/deploy-block-header-requester"); } catch {}
try { require("./ping/deploy/deploy-ping-sender"); } catch {}
try { require("./ping/deploy/deploy-ping-receiver"); } catch {}
try { require("./ping/deploy/deploy-ping-cross-chain"); } catch {}

// Ping operation tasks (optional deps)
try { require("./ping/ping/send-ping"); } catch {}
try { require("./ping/ping/check-ping"); } catch {}
try { require("./ping/ping/generate-proof"); } catch {}
try { require("./ping/ping/relay-message"); } catch {}

// Paymaster tasks
import "./paymaster/deploy/deploy-paymaster-vault";
import "./paymaster/deploy/upgrade-paymaster-vault";
import "./paymaster/deploy/deploy-cross-chain-paymaster";
import "./paymaster/deploy/upgrade-cross-chain-paymaster";
import "./paymaster/deploy/deploy-mock-oracle";
import "./paymaster/post/configure-cross-chain-paymaster";
import "./paymaster/post/configure-paymaster-vault";
import "./paymaster/post/configure-mock-price-oracle";
// Paymaster payment flow tasks
import "./paymaster/pay/deposit-token";
import "./paymaster/pay/generate-proof";
import "./paymaster/pay/relay-payment";

// General utility tasks
import "./post-blockhash";
