# Review sheet: runs/decoy/tau/sonnet-medium

Model `claude-sonnet-5-5`, effort `medium`, domain `tau`.
Flags come from Tau-specific heuristics in this review script, not from the generator.
Fill `decision` (accept/reject), `reviewer` and `reason` in `reviews.json`; blanks are refused at release.
Suggestions: 28 accept, 0 reject; 31 has no candidate (one decoy placed after the root failure).


## Trajectory 2
**Root failure:** step 7 → 11 in the variant. At step 7, the agent did not correctly count the number of available t-shirts from the tool call result.

**Model's rationale:** A mistyped product ID lookup that errors before the successful retry adds a visible error just before the failure. A replayed product-type listing between the product details and the agent's count adds extra output after the evidence and before the miscount.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 5 is the retry | ok |
| noise | 9–10 | replays steps 3–4 (`list_all_product_types {}`) after step 6 | ok |

**Suggested:** accept

## Trajectory 3
**Root failure:** step 7 → 11 in the variant. At step 7, the agent did not correctly count the number of available t-shirts from the tool call result.

**Model's rationale:** A failed product lookup with a transposed ID, then a retry, adds an apparent error just before the failure. A replay of the same product-details read puts more output between the data and the miscount. This diverts attention from the miscount in step 7.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 5 is the retry | ok |
| noise | 9–10 | replays steps 5–6 (`get_product_details {"product_id":"9523456873"}`) after step 6 | ok |

**Suggested:** accept

## Trajectory 4
**Root failure:** step 15 → 19 in the variant. At step 15, the assistant agent incorrectly counted the number of available t-shirts.

**Model's rationale:** A profile re-read and a failed product lookup with a mistyped ID appear just before the T-shirt listing is read. This puts extra output and an error right before the miscount at step 15. The error looks like trouble, but the retry succeeds and the result is unchanged.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| noise | 13–14 | replays steps 9–10 (`get_user_details {"user_id":"yusuf_rossi_9620"}`) after step 12 | ok |
| red_herring | 15–16 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 13 is the retry | ok |

**Suggested:** accept

## Trajectory 12
**Root failure:** step 19 → 23 in the variant. At step 19, the assistant agent did not ask user for confirmation and payment method before initiating return.

**Model's rationale:** A failed order lookup early on adds a visible error unrelated to the later return. A replayed read-only order lookup right before the return call adds extra output between the evidence and the premature write action.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W5490111` → `#W5490119`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 21–22 | replays steps 13–14 (`get_order_details {"order_id":"#W7387996"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 20
**Root failure:** step 21 → 25 in the variant. At step 21, the assistant mistook two of the orders which were processed as delivered

**Model's rationale:** A failed authentication lookup early adds a visible error that is harmlessly self-corrected. A replayed profile read sits between the order status evidence and the assistant's misreading, adding output in between.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 7–8 | `find_user_id_by_name_zip` with `Garcia` → `Garcai`, answered `Error: user not found`; original step 7 is the retry | ok |
| noise | 21–22 | replays steps 9–10 (`get_user_details {"user_id":"ethan_garcia_1261"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 21
**Root failure:** step 28 → 34 in the variant. At step 28, the user agent insisted on exchange of an item in 'pending' status which is not valid according to domain policy, when assistant asked if it could instead modify (corresponds to the ground truth), the user agent said no.

**Model's rationale:** A failed order lookup with a transposed ID sits just before the pending-order discovery. Re-reading the order and the shoe product just before the assistant refuses the exchange adds read-only output near the failure. Both draw attention to the order status without changing it.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W9911714` → `#W9911741`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 19–20 | replays steps 13–14 (`get_order_details {"order_id": "#W9911714"}`) after step 16 | ok |
| noise | 31–32 | replays steps 23–24 (`get_product_details {"product_id":"6938111410"}`) after step 26 | ok |

**Suggested:** accept

## Trajectory 28
**Root failure:** step 33 → 37 in the variant. At step 33,  the assistant mistakenly believes that it can cancel a subset of a pending order which is not allowed as per domain policy, as a result the entire order got cancelled instead of just the garden hose.

**Model's rationale:** A failed order lookup with a mistyped ID appears early and is retried successfully, adding a visible error. A re-read of the pending order right before the cancel call puts extra output between the evidence and the failing call. Neither changes the agent's later wrong assumption that a partial cancel is possible.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 17–18 | `get_order_details` with `#W2575533` → `#W2575553`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 35–36 | replays steps 17–18 (`get_order_details {"order_id":"#W2575533"}`) after step 32 | writes in between on other entities: step 23 `return_delivered_order_items`, step 25 `return_delivered_order_items`, step 27 `return_delivered_order_items` |

**Suggested:** accept

## Trajectory 31
No release candidate: A red herring copies a request and its response, both before the root failure

## Trajectory 32
**Root failure:** step 11 → 15 in the variant. At step 11, the assistant mistakenly provided tracking number of wrong order which did not even contain the tablet.

**Model's rationale:** A mistyped order ID lookup that returns an error just before the real lookup adds a visible error near the failure. A replayed profile read between the order output and the wrong answer adds extra output between the evidence and the mistake.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_order_details` with `#W7449508` → `#W7449580`, answered `Error: order not found`; original step 9 is the retry | ok |
| noise | 13–14 | replays steps 7–8 (`get_user_details {"user_id":"olivia_lopez_3865"}`) after step 10 | ok |

**Suggested:** accept

## Trajectory 34
**Root failure:** step 17 → 21 in the variant. At step 17, the assistant uses modify order to cancel a subset of orders, however modify orders also need to have a replacement, which it did not provide resulting in an illegal tool call

**Model's rationale:** A failed profile lookup early on adds a visible error unrelated to the later failure. A replayed order read right before the modify call adds extra output between the user's confirmation and the faulty tool call.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_user_details` with `noah_patel_6952` → `noah_patel_6925`, answered `Error: user not found`; original step 9 is the retry | ok |
| noise | 19–20 | replays steps 11–12 (`get_order_details {"order_id":"#W1845024"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 38
**Root failure:** step 37 → 43 in the variant. At step 37, for the umbrella, it picks an item that is cheapest but is not available. the assistant is not able to correctly compare the item prices to figure which is the cheapest one.

**Model's rationale:** A failed umbrella product lookup with a transposed digit appears just before the umbrella data, so it looks like trouble with the umbrella. The replayed order and profile reads put extra output between the product data and the faulty price calculation. Both are harmless read-only calls.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 27–28 | `get_product_details` with `9743693396` → `9743639396`, answered `Error: product not found`; original step 27 is the retry | ok |
| noise | 39–40 | replays steps 13–14 (`get_order_details {"order_id":"#W9348897"}`) after step 34 | ok |
| noise | 35–36 | replays steps 11–12 (`get_user_details {"user_id":"daiki_sanchez_3253"}`) after step 32 | ok |

**Suggested:** accept

## Trajectory 39
**Root failure:** step 17 → 23 in the variant. At step 17, the assistant agent believes that it cannot find the latest address from the current orders using get_order_details and hence is unable to modify the existing user address in an order to the latest one.

**Model's rationale:** Two harmless failed lookups (typo'd name, transposed user id) add visible errors during authentication, and a replayed profile read right before the failure puts extra output between the user's request and the agent's mistaken claim.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `find_user_id_by_name_zip` with `Fatima` → `Fatmia`, answered `Error: user not found`; original step 9 is the retry | ok |
| red_herring | 13–14 | `get_user_details` with `fatima_taylor_3452` → `fatima_taylor_3542`, answered `Error: user not found`; original step 11 is the retry | ok |
| noise | 21–22 | replays steps 11–12 (`get_user_details {"user_id":"fatima_taylor_3452"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 41
**Root failure:** step 17 → 23 in the variant. At step 17, the assistant agent modified the items in the pending order which locked it and hence cannot update the shipping address later, hence the order of tool calling should have been vice-versa.

**Model's rationale:** A failed authentication lookup adds an early, harmless error. Re-reading the pending order and the jigsaw product details right before the modify call adds extra output between the user's request and the mistaken tool call. The real error is still the order of operations, which none of these changes.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_name_zip` with `Patel` → `Patell`, answered `Error: user not found`; original step 5 is the retry | ok |
| noise | 19–20 | replays steps 11–12 (`get_order_details {"order_id":"#W4082615"}`) after step 16 | ok |
| noise | 19–20 | replays steps 13–14 (`get_product_details {"product_id":"1808611083"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 47
**Root failure:** step 19 → 23 in the variant. At step 19, the assistant prematurely called transfer to human tool whereas it should have first called the return order tool

**Model's rationale:** A failed order lookup with a transposed digit adds a visible error early in the trajectory. A re-read of the order details right before the transfer adds extra output between the evidence and the failing step. Neither one changes what the agent does at step 19.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W9502127` → `#W9502172`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 21–22 | replays steps 13–14 (`get_order_details {"order_id":"#W9502127"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 55
**Root failure:** step 32 → 38 in the variant. The user asked the assistant to return the air purifier, smart watch, and coffee maker while it should have also asked it to return the water bottle from the order according to the task instruction.

**Model's rationale:** A failed lookup of the order that contains the four items, plus re-reads of the profile and of that order close to the return request, add error-like and bulky output near the point where the user lists items. This pulls attention to the lookups and the assistant's handling, away from the user's incomplete item list.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 17–18 | `get_order_details` with `#W4597054` → `#W4597045`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 35–36 | replays steps 17–18 (`get_order_details {"order_id": "#W4597054"}`) after step 30 | writes in between on other entities: step 27 `cancel_pending_order`, step 29 `cancel_pending_order` |
| noise | 27–28 | replays steps 9–10 (`get_user_details {"user_id":"amelia_silva_7726"}`) after step 24 | ok |

**Suggested:** accept

## Trajectory 59
**Root failure:** step 14 → 18 in the variant. The user agent incorrectly assumed that one order was older than the other even when the assistant specifically mentioned that it did not have the chronological information regarding the orders' placement date. It led to the incorrect order being cancelled compared to ground truth actions.

**Model's rationale:** A failed order lookup followed by a successful retry adds apparent trouble early on. A replayed read of order #W2702727 puts extra output between the order data and the user's later decision. Neither changes the user's unsupported assumption at step 14.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_order_details` with `#W8268610` → `#W8268601`, answered `Error: order not found`; original step 9 is the retry | ok |
| noise | 13–14 | replays steps 7–8 (`get_order_details {"order_id": "#W2702727"}`) after step 10 | ok |

**Suggested:** accept

## Trajectory 63
**Root failure:** step 32 → 40 in the variant. In step 32, the user agent asked the assistant to add an item to a pending order instead of replacing it with the cheaper item. This is because of unclear original task instruction.

**Model's rationale:** Early failed lookups with typos and replayed order and product reads add visible errors and extra output before the user's step 32 reply, pulling attention toward lookup problems and the assistant's reads.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W5061109` → `#W5061190`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `4768869376` → `4768869367`, answered `Error: product not found`; original step 15 is the retry | ok |
| noise | 29–30 | replays steps 15–16 (`get_product_details {"product_id":"4768869376"}`) after step 24 | ok |
| noise | 37–38 | replays steps 13–14 (`get_order_details {"order_id":"#W5061109"}`) after step 30 | ok |

**Suggested:** accept

## Trajectory 71
**Root failure:** step 24 → 30 in the variant. At step 24, the task instruction did not specify the type of black lamp and since there are multiple black lamps available, it wont be possible to match the ground truth actions.

**Model's rationale:** Two harmless lookup errors (mistyped order ID and product ID) that are immediately retried add visible errors before the failure. A re-read of the user profile puts extra output between the lamp options and the user's choice. None of these change state or excuse the underspecified user choice.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W5270061` → `#W5270016`, answered `Error: order not found`; original step 15 is the retry | ok |
| red_herring | 21–22 | `get_product_details` with `6817146515` → `6817146551`, answered `Error: product not found`; original step 19 is the retry | ok |
| noise | 27–28 | replays steps 11–12 (`get_user_details {"user_id":"ivan_khan_7475"}`) after step 22 | ok |

**Suggested:** accept

## Trajectory 72
**Root failure:** step 21 → 27 in the variant. At step 21, the assistant modifies order items before modifying address which locks in the order and hence is unable to modify the shipping address later.

**Model's rationale:** Two harmless failed lookups (a mistyped order ID and a mistyped product ID) that are retried successfully add visible errors early on. A replayed profile read just before the plan and the modify call puts extra output between the evidence and the failure. None of these change the later flawed ordering of the modify-items call before the address change.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W5270061` → `#W5270016`, answered `Error: order not found`; original step 11 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `2524789262` → `2524789226`, answered `Error: product not found`; original step 15 is the retry | ok |
| noise | 23–24 | replays steps 7–8 (`get_user_details {"user_id":"ivan_khan_7475"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 74
**Root failure:** step 21 → 27 in the variant. At step 21, the agent called exchange order items tool on an order which is still in pending status which is invalid.

**Model's rationale:** A failed order lookup with a transposed digit adds an early visible error. Two replays of the read-only profile lookup put extra output between the order evidence and the faulty exchange call, so attention is pulled away from step 21.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W5166363` → `#W5166336`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 17–18 | replays steps 9–10 (`get_user_details {"user_id":"lei_li_6575"}`) after step 14 | ok |
| noise | 23–24 | replays steps 9–10 (`get_user_details {"user_id":"lei_li_6575"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 79
**Root failure:** step 20 → 26 in the variant. The task instruction did not specify the color of the 1000ml bottle to be exchanged whether it was red or black. Because of this ambiguity, the user agent picked the black bottle whereas the ground truth as the red variant which did not correspond with the ground truth actions. The red variant instead matched the ground truth.

**Model's rationale:** Two harmless failed lookups with typos, each followed by the successful original, add visible errors before the user's choice. A replayed product-details read adds extra output between the variant list and the user's pick of the black bottle.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W9284598` → `#W9284589`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 19–20 | `get_product_details` with `8310926033` → `8310926330`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 23–24 | replays steps 17–18 (`get_product_details {"product_id":"8310926033"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 80
**Root failure:** step 26 → 32 in the variant. The execution of the assistant ended prematurely because of system failure.

**Model's rationale:** Two failed lookups with slipped IDs, each retried correctly, add visible errors early. A re-read of the order details just before the final turn adds extra output between the evidence and the failure at step 26.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_user_details` with `amelia_gonzalez_4098` → `amelia_gonzalez_4089`, answered `Error: user not found`; original step 11 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 15 is the retry | ok |
| noise | 29–30 | replays steps 13–14 (`get_order_details {"order_id": "#W7209932"}`) after step 24 | ok |

**Suggested:** accept

## Trajectory 82
**Root failure:** step 20 → 26 in the variant. At step 20, the user agent asked the assistant to the return the tablets from both the orders, however, it was supposed to ask to return all the items from a single order, hence, did not follow the task instruction

**Model's rationale:** Two harmless order-ID typo lookups that fail with "order not found" and are retried, plus a re-read of the user profile just before the assistant's summary. These put visible errors and extra output near the tablet and refund-method evidence. They draw attention toward assistant lookup slips, away from the user's step-20 request to return both tablets.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W3069600` → `#W3096600`, answered `Error: order not found`; original step 11 is the retry | ok |
| red_herring | 19–20 | `get_order_details` with `#W9571698` → `#W9571689`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 23–24 | replays steps 7–8 (`get_user_details {"user_id":"chen_silva_7485"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 87
**Root failure:** step 37 → 41 in the variant. The assistant agent should have modified all the three pending order addresses but it only modified the first two pending order addresses and claimed that it completed all the updates.

**Model's rationale:** A failed order lookup with a transposed ID, then a successful retry, adds visible trouble just before the address is found. A replayed profile read puts extra output between the order evidence and the update calls. Neither one touches the missing third order update.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 27–28 | `get_order_details` with `#W1994898` → `#W1994889`, answered `Error: order not found`; original step 27 is the retry | ok |
| noise | 31–32 | replays steps 9–10 (`get_user_details {"user_id":"yusuf_hernandez_6785"}`) after step 28 | ok |

**Suggested:** accept

## Trajectory 91
**Root failure:** step 34 → 40 in the variant. The user agent asked the assistant to also return the tablet from order #W3239882, however, this was not specified in the original task instruction.

**Model's rationale:** Two harmless failed lookups (mistyped order and product IDs) that are retried successfully add visible errors early in the trajectory. A re-read of the user profile just before the user's unrequested tablet request adds extra output between the evidence and the failure step.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W3239882` → `#W3239822`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 19–20 | `get_product_details` with `3801771308` → `3801771380`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 37–38 | replays steps 7–8 (`get_user_details {"user_id":"mei_ahmed_4909"}`) after step 32 | ok |

**Suggested:** accept

## Trajectory 98
**Root failure:** step 21 → 27 in the variant. The assistant agent first modified the items in the pending orders before modifying the addresses which locked the orders and hence couldn't update the shipping addresses later. The correct sequence should have been vice-versa.

**Model's rationale:** A failed order lookup with a typo'd ID right before the failure adds a visible error. The replayed profile and product reads then sit between the evidence (the NYC order was fetched at step 20) and the faulty modify_pending_order_items call. Together they pull attention to lookups instead of the ordering mistake.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 19–20 | `get_order_details` with `#W3407479` → `#W3407749`, answered `Error: order not found`; original step 19 is the retry | ok |
| noise | 23–24 | replays steps 7–8 (`get_user_details {"user_id":"yusuf_li_7255"}`) after step 20 | writes in between on other entities: step 15 `exchange_delivered_order_items` |
| noise | 23–24 | replays steps 11–12 (`get_product_details {"product_id":"4768869376"}`) after step 20 | writes in between on other entities: step 15 `exchange_delivered_order_items` |

**Suggested:** accept (checked: profile has no balance field and no profile write in between)

## Trajectory 99
**Root failure:** step 35 → 43 in the variant. The assistant while exchanging the delivered order items used the incorrect credit card. The task instruction and consequently the user mentions to use the other credit card on file, but it uses the same credit card. This could have been avoided if the assistant had confirmed the payment method with the user before proceeding with the exchange.

**Model's rationale:** Failed lookups with typos in the product ID and order ID add visible errors before the camera exchange. Re-reading the order and the profile just before the exchange call puts extra output between the user's request and the faulty payment_method_id. That could make an evaluator blame lookup slips or stale data rather than the payment choice.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 33–34 | `get_product_details` with `8940227892` → `8940227829`, answered `Error: product not found`; original step 31 is the retry | ok |
| red_herring | 11–12 | `get_order_details` with `#W4689314` → `#W4689341`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 41–42 | replays steps 11–12 (`get_order_details {"order_id": "#W4689314"}`) after step 34 | writes in between on other entities: step 29 `exchange_delivered_order_items` |
| noise | 37–38 | replays steps 9–10 (`get_user_details {"user_id":"sofia_li_9219"}`) after step 32 | writes in between on other entities: step 29 `exchange_delivered_order_items` |

**Suggested:** accept (checked: profile has no balance field and no profile write in between)

## Trajectory 104
**Root failure:** step 57 → 61 in the variant. The assistant mentioned to the user that the cancelled order #W1154986 did not have a tracking number. However, this is not true as in the tool output of get_order_details for order #W1154986, a tracking number is clearly present.

**Model's rationale:** A failed lookup of the same cancelled order that the final failure concerns draws attention to an error about that order. A profile re-read right before the faulty answer adds extra output between the evidence and the mistake.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W1154986` → `#W1154968`, answered `Error: order not found`; original step 15 is the retry | ok |
| noise | 59–60 | replays steps 7–8 (`get_user_details {"user_id":"lucas_brown_6720"}`) after step 56 | writes in between on other entities: step 27 `return_delivered_order_items`, step 35 `return_delivered_order_items`, step 43 `modify_pending_order_address`, step 53 `modify_pending_order_items` |

**Suggested:** accept (checked: profile has no balance field and no profile write in between)

## Trajectory 105
**Root failure:** step 43 → 47 in the variant. The assistant tries to modify the address after the modifying the pending order items which is not supported currently per the domain policy.

**Model's rationale:** A visible order-not-found error appears in the earlier backpack lookup, and a profile re-read sits between the user's address request and the failing address call. Both add unrelated output and look like trouble, but neither changes the order state or the assistant's decision at step 43.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| noise | 45–46 | replays steps 9–10 (`get_user_details {"user_id":"lucas_brown_6720"}`) after step 42 | writes in between on other entities: step 17 `return_delivered_order_items`, step 19 `return_delivered_order_items`, step 29 `return_delivered_order_items`, step 39 `modify_pending_order_items` |
| red_herring | 25–26 | `get_order_details` with `#W9218746` → `#W9218764`, answered `Error: order not found`; original step 25 is the retry | ok |

**Suggested:** accept (checked: profile has no balance field and no profile write in between)

