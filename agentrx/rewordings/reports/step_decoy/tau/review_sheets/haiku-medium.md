# Review sheet: runs/decoy/tau/haiku-medium

Model `claude-haiku-5-5`, effort `medium`, domain `tau`.
Flags come from Tau-specific heuristics in this review script, not from the generator.
Fill `decision` (accept/reject), `reviewer` and `reason` in `reviews.json`; blanks are refused at release.
Suggestions: 28 accept, 1 reject (28: stale replay after a return of the same order).


## Trajectory 2
**Root failure:** step 7 → 11 in the variant. At step 7, the agent did not correctly count the number of available t-shirts from the tool call result.

**Model's rationale:** The red herring places a visible tool error (a transposed T-Shirt product ID, 9523456783) directly before the correct get_product_details lookup, so the trajectory appears to contain a failed lookup just before the count. The noise replays the same read-only product details lookup right after the tool result and before the answer, adding a second copy of the variant list for the evaluator to sort through. Neither changes the data the agent sees, so the miscount at step 7 remains the only error in the answer.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `get_product_details` with `9523456873` → `9523456783`, answered `Error: product not found`; original step 5 is the retry | ok |
| noise | 9–10 | replays steps 5–6 (`get_product_details {"product_id":"9523456873"}`) after step 6 | ok |

**Suggested:** accept

## Trajectory 3
**Root failure:** step 7 → 11 in the variant. At step 7, the agent did not correctly count the number of available t-shirts from the tool call result.

**Model's rationale:** The annotated failure is a miscount at step 7: the get_product_details result at step 6 lists 12 variants, of which two (5047954489 and 3542102174) are unavailable, so 10 are available, but the agent said 11. The red herring is a transposed-digit product ID on the step 5 lookup that returns a plain not-found error before the correct retry, which adds a visible error right before the evidence and makes the product lookup look shaky, pulling attention toward the tool-call stage rather than the count. The noise replays the harmless product-type listing right between the product details result and the final answer, lengthening the output the evaluator must sift through before the miscount.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `get_product_details` with `9523456873` → `9523456783`, answered `Error: product not found`; original step 5 is the retry | ok |
| noise | 9–10 | replays steps 3–4 (`list_all_product_types {}`) after step 6 | ok |

**Suggested:** accept

## Trajectory 4
**Root failure:** step 15 → 19 in the variant. At step 15, the assistant agent incorrectly counted the number of available t-shirts.

**Model's rationale:** The red herring adds a visible failed product lookup just before the real product-details call, so the evaluator sees a lookup error and a successful retry near the miscount, which may distract from the actual counting error. The noise replays the read-only product-type listing between the product output and the count, adding unrelated tool output right before the failure without changing any state. Neither decoy alters the product data that step 14 returns, so the count error at step 15 remains the only mistake.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 13 is the retry | ok |
| noise | 17–18 | replays steps 11–12 (`list_all_product_types {}`) after step 14 | ok |

**Suggested:** accept

## Trajectory 12
**Root failure:** step 19 → 23 in the variant. At step 19, the assistant agent did not ask user for confirmation and payment method before initiating return.

**Model's rationale:** The red herring adds a visible, harmless lookup failure on the order ID before the agent correctly fetches #W5490111 for the first time, which makes the order-lookup phase look like the place where things went wrong. The noise replays the read-only profile lookup right after the user says to cancel or return everything, so the assistant appears to be re-checking account details before acting. Both are plausible, read-only, and leave the state unchanged, so they draw attention away from the return at step 19 without altering it.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W5490111` → `#W5490101`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 19–20 | replays steps 7–8 (`get_user_details {"user_id":"mia_garcia_4516"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 20
**Root failure:** step 21 → 27 in the variant. At step 21, the assistant mistook two of the orders which were processed as delivered

**Model's rationale:** Two order-ID slips (a transposed digit in #W9911714 and #W5733668) return "order not found" just before the successful lookups, so the trajectory shows visible lookup errors in the same stretch where the order statuses are being gathered. The noise replay of get_user_details sits between the user's upgrade request and the failing reply, adding a read-only exchange that lengthens the gap between the status evidence at step 18/19 and the misreading at step 21. Together these make an evaluator more likely to attribute the trouble to a lookup error or to the profile read rather than to the status misreading.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W9911714` → `#W9911741`, answered `Error: order not found`; original step 15 is the retry | ok |
| red_herring | 19–20 | `get_order_details` with `#W5733668` → `#W5733686`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 25–26 | replays steps 9–10 (`get_user_details {"user_id":"ethan_garcia_1261"}`) after step 20 | ok |

**Suggested:** accept

## Trajectory 21
**Root failure:** step 28 → 32 in the variant. At step 28, the user agent insisted on exchange of an item in 'pending' status which is not valid according to domain policy, when assistant asked if it could instead modify (corresponds to the ground truth), the user agent said no.

**Model's rationale:** The red herring adds a visible, self-corrected lookup failure on the order ID before the order is found. A reader scanning for errors may fixate on it as the source of the confusion, when the retry succeeds and changes nothing. The noise replays a read-only product lookup for the shoes right after the user's "I still need to exchange them" message, which adds output between the user's pushback and the assistant's refusal. Both draw attention away from step 28, where the user rejects the valid modify option.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `"order_id": "#W9911714"` → `"order_id": "#W9911741"`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 29–30 | replays steps 23–24 (`get_product_details {"product_id":"6938111410"}`) after step 26 | ok |

**Suggested:** accept

## Trajectory 28
**Root failure:** step 33 → 37 in the variant. At step 33,  the assistant mistakenly believes that it can cancel a subset of a pending order which is not allowed as per domain policy, as a result the entire order got cancelled instead of just the garden hose.

**Model's rationale:** The red herring adds a visible "order not found" error for a transposed order ID shortly before the agent looks up #W2575533 again. The retry succeeds and shows the pending order, so the error looks like a lookup problem, not a policy issue, and draws attention to order-ID handling rather than to the cancellation scope. The noise re-reads order #W7181492, which contains a different garden hose (item 5753502325, not the one in #W2575533). Its unchanged contents add a second hose and a second order to compare right before the cancel call, which can make the agent think the hose is separable from its order.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 17–18 | `get_order_details` with `#W2575533` → `#W2575553`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 35–36 | replays steps 13–14 (`get_order_details {"order_id": "#W7181492"}`) after step 32 | stale: step 25 `return_delivered_order_items` on the same entity |

**Suggested:** reject (stale: step 25 `return_delivered_order_items` on the same entity)

## Trajectory 31
**Root failure:** step 31 → 35 in the variant. At step 31, the assistant mistakenly believes that it can cancel a subset of a pending order which is not allowed as per domain policy, as a result the entire order got cancelled instead of just the hiking boots.

**Model's rationale:** The red herring is a transposed order ID on the read-only lookup of the boot order, answered by a not-found error. It looks like a trouble spot in the boot-cancellation flow but is harmless, so it draws attention to order-ID handling rather than to the cancel call. The noise decoy re-reads the same boot order (#W5481803) between the user's confirmation and the cancel call. It is a state-free read whose result is unchanged, and it lengthens the stretch of output the evaluator must sift through before the wrong cancel_pending_order call at step 31.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 27–28 | `get_order_details` with `#W5481803` → `#W5481830`, answered `Error: order not found`; original step 27 is the retry | ok |
| noise | 33–34 | replays steps 27–28 (`get_order_details {"order_id":"#W5481803"}`) after step 30 | ok |

**Suggested:** accept

## Trajectory 32
**Root failure:** step 11 → 15 in the variant. At step 11, the assistant mistakenly provided tracking number of wrong order which did not even contain the tablet.

**Model's rationale:** The red herring adds a visible "order not found" error for a transposed order ID just before the agent reads the correct order #W7449508, so the agent appears to be retrying a failed lookup and the error draws attention to order-ID handling rather than to the content of the tool output. The noise replays the read-only get_user_details call right after the order details, lengthening the trajectory between the evidence and the answer at step 11 without changing any state or result.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_order_details` with `#W7449508` → `#W7494508`, answered `Error: order not found`; original step 9 is the retry | ok |
| noise | 13–14 | replays steps 7–8 (`get_user_details {"user_id":"olivia_lopez_3865"}`) after step 10 | ok |

**Suggested:** accept

## Trajectory 34
**Root failure:** step 17 → 21 in the variant. At step 17, the assistant uses modify order to cancel a subset of orders, however modify orders also need to have a replacement, which it did not provide resulting in an illegal tool call

**Model's rationale:** The red herring adds an early, harmless lookup failure on a transposed order ID, which draws attention to order-ID handling and makes the assistant look error-prone before the real problem. The noise replays the read-only order lookup right after the user's confirmation, so the order's item list appears again between the user's yes and the faulty modify call, pulling focus toward item details rather than the malformed argument lists. Neither decoy changes state or alters the later steps.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W1845024` → `#W1845042`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 19–20 | replays steps 11–12 (`get_order_details {"order_id":"#W1845024"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 38
**Root failure:** step 37 → 43 in the variant. At step 37, for the umbrella, it picks an item that is cheapest but is not available. the assistant is not able to correctly compare the item prices to figure which is the cheapest one.

**Model's rationale:** The annotated failure is the choice of the 285.66 umbrella (item 3111466194, unavailable) as the cheapest umbrella at step 37. The red herring is a failed lookup of the Patio Umbrella product with a transposed digit in its product ID, which produces an error right before the correct umbrella lookup. It draws attention to the umbrella product data and makes the umbrella step look like the point where the agent struggled. The noise replays re-read the Action Camera product details (between the umbrella data and the calculation) and the order details (just before the calculation). These are read-only, return identical results, and add output between the umbrella evidence and the failing calculation, diluting attention on the umbrella step.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 27–28 | `get_product_details` with `9743693396` → `9743693369`, answered `Error: product not found`; original step 27 is the retry | ok |
| noise | 37–38 | replays steps 25–26 (`get_product_details {"product_id": "3377618313"}`) after step 34 | ok |
| noise | 41–42 | replays steps 13–14 (`get_order_details {"order_id":"#W9348897"}`) after step 36 | ok |

**Suggested:** accept

## Trajectory 39
**Root failure:** step 17 → 21 in the variant. At step 17, the assistant agent believes that it cannot find the latest address from the current orders using get_order_details and hence is unable to modify the existing user address in an order to the latest one.

**Model's rationale:** The red herring adds a visible "user not found" error for a read-only profile lookup just before the successful retry, which draws attention to account-lookup problems instead of the order-details check. The noise replay re-reads the user profile right after the customer says the new address may be in their order, so the agent's attention is spread over profile data it already has, close to the step where it wrongly decides the order details are unusable. Neither decoy changes the state or the authentication outcome, and the successful retry and all later steps stay as in the original.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_user_details` with `fatima_taylor_3452` → `fatima_taylor_3425`, answered `Error: user not found`; original step 11 is the retry | ok |
| noise | 19–20 | replays steps 11–12 (`get_user_details {"user_id":"fatima_taylor_3452"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 41
**Root failure:** step 17 → 21 in the variant. At step 17, the assistant agent modified the items in the pending order which locked it and hence cannot update the shipping address later, hence the order of tool calling should have been vice-versa.

**Model's rationale:** The red herring makes a read-only order lookup fail with a transposed digit in the order ID just before the agent looks up the same order correctly, which draws attention to order-ID handling rather than to sequencing. The noise replays the read-only user profile lookup right after the user's address correction request, so the address discussion is followed by extra profile output that still shows the old address and no sign of the ordering problem. Together they put distracting, harmless output between the user's address request and the item modification at step 17.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W4082615` → `#W4082651`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 19–20 | replays steps 7–8 (`get_user_details {"user_id":"mei_patel_7272"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 47
**Root failure:** step 19 → 23 in the variant. At step 19, the assistant prematurely called transfer to human tool whereas it should have first called the return order tool

**Model's rationale:** The red herring is a mistyped order ID lookup (#W9502172) that fails with "order not found" just before the agent correctly looks up #W9502127, which makes the early lookup phase look like the place where things went wrong and draws attention to order identification. The noise replays the read-only order lookup for #W9502127 right after the user's escalation request, so the agent appears to be re-checking the order, while the actual premature transfer at step 19 still follows.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W9502127` → `#W9502172`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 21–22 | replays steps 13–14 (`get_order_details {"order_id":"#W9502127"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 55
**Root failure:** step 32 → 36 in the variant. The user asked the assistant to return the air purifier, smart watch, and coffee maker while it should have also asked it to return the water bottle from the order according to the task instruction.

**Model's rationale:** The red herring adds a visible failed order lookup (a transposed digit in #W4597054) followed by a successful retry, which draws attention to order #W4597054 early and makes the agent's handling of that order look error-prone. The noise replays the read-only get_order_details for #W4597054 just before the user's final return request, placing the water bottle line item in view again while the user is still deciding. Neither decoy changes the order state or the user's later message, so the annotated omission of the water bottle from the return request stays the root cause.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 17–18 | `get_order_details` with `#W4597054` → `#W4579054`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 33–34 | replays steps 17–18 (`get_order_details {"order_id": "#W4597054"}`) after step 30 | writes in between on other entities: step 27 `cancel_pending_order`, step 29 `cancel_pending_order` |

**Suggested:** accept

## Trajectory 59
**Root failure:** step 14 → 18 in the variant. The user agent incorrectly assumed that one order was older than the other even when the assistant specifically mentioned that it did not have the chronological information regarding the orders' placement date. It led to the incorrect order being cancelled compared to ground truth actions.

**Model's rationale:** The red herring adds an early, self-corrected lookup error on the older order ID, a visible error that looks like trouble before the agent reads the real order details. The noise replays the read-only lookup of order #W8268610 between the user's refund question and the agent's reply, so the two orders' details sit side by side just before the user's cancellation request at step 14. Neither decoy changes any state or alters the order data that follows.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 7–8 | `get_order_details` with `#W2702727` → `#W2702772`, answered `Error: order not found`; original step 7 is the retry | ok |
| noise | 15–16 | replays steps 9–10 (`get_order_details {"order_id":"#W8268610"}`) after step 12 | ok |

**Suggested:** accept

## Trajectory 63
**Root failure:** step 32 → 36 in the variant. In step 32, the user agent asked the assistant to add an item to a pending order instead of replacing it with the cheaper item. This is because of unclear original task instruction.

**Model's rationale:** The red herring adds an early visible lookup failure on the order ID, which looks like a data problem that the agent later resolves, pulling attention toward order-lookup errors rather than the user's request at step 32. The noise decoy replays the read-only product lookup right after the user asks to add the cheaper speaker, so extra tool output sits between the request and the assistant's reply, lengthening the trajectory and diluting focus on the user's decision to keep the expensive speaker and add the cheaper one instead of replacing it.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W5061109` → `#W5061190`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 33–34 | replays steps 15–16 (`get_product_details {"product_id":"4768869376"}`) after step 30 | ok |

**Suggested:** accept

## Trajectory 71
**Root failure:** step 24 → 28 in the variant. At step 24, the task instruction did not specify the type of black lamp and since there are multiple black lamps available, it wont be possible to match the ground truth actions.

**Model's rationale:** The red herring makes the agent mistype the desk lamp product ID (a transposed digit) on the lookup that starts the lamp change, which the system rejects with a "product not found" error before the correct lookup succeeds. That early visible error in the lamp-modification flow can draw attention toward the product lookup rather than the later user choice. The noise replays the read-only profile lookup right after the agent's "think" step and before it lists the black lamp options, adding output between the evidence and the failure without changing state. Neither decoy alters the options the agent presents or what the user later picks.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 19–20 | `get_product_details` with `6817146515` → `6817146551`, answered `Error: product not found`; original step 19 is the retry | ok |
| noise | 25–26 | replays steps 11–12 (`get_user_details {"user_id":"ivan_khan_7475"}`) after step 22 | ok |

**Suggested:** accept

## Trajectory 72
**Root failure:** step 21 → 27 in the variant. At step 21, the assistant modifies order items before modifying address which locks in the order and hence is unable to modify the shipping address later.

**Model's rationale:** The red herring is a failed lookup of the desk lamp product with a transposed digit in its product ID, which is harmless because it only reads data and the correct retry follows immediately, so it looks like a routine retry rather than a mistake. The two noise replays re-read the backpack product details and the order details between the last lookup and the think step. Both are read-only and return the same results, so they add output between the agent's evidence and the modify_pending_order_items call without changing any state. These spread attention across many lookups and make the address-first requirement look less central.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 17–18 | `get_product_details` with `6817146515` → `6817164515`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 21–22 | replays steps 15–16 (`get_product_details {"product_id": "2524789262"}`) after step 18 | ok |
| noise | 21–22 | replays steps 11–12 (`get_order_details {"order_id": "#W5270061"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 74
**Root failure:** step 21 → 25 in the variant. At step 21, the agent called exchange order items tool on an order which is still in pending status which is invalid.

**Model's rationale:** The red herring adds an earlier "order not found" error from a transposed order ID on a read-only lookup, which the agent then corrects by retrying the correct ID. This draws attention to order-lookup errors and makes the order-ID handling look like the source of trouble, while the actual problem (exchanging a pending order) is not touched. The noise replays the read-only product-details lookup between the user's answers and the confirmation, lengthening the trajectory with unchanged output before the confirmation and the failing call.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W5166363` → `#W5166336`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 21–22 | replays steps 13–14 (`get_product_details {"product_id":"4760268021"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 79
**Root failure:** step 20 → 24 in the variant. The task instruction did not specify the color of the 1000ml bottle to be exchanged whether it was red or black. Because of this ambiguity, the user agent picked the black bottle whereas the ground truth as the red variant which did not correspond with the ground truth actions. The red variant instead matched the ground truth.

**Model's rationale:** The red herring makes the first product lookup look like a failed call: the agent mistypes the water bottle product ID, gets a not-found error, and then retries with the correct ID. This adds a visible error just before the agent lists the replacement options, which can draw attention to the lookup and away from the choice at step 20. The noise replays the agent's read of order #W9284598 right after the product details. That order contains the 1000ml red glass bottle and other items, so the evaluator sees more 1000ml bottle data and more chances to mistake the red and black variants.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 17–18 | `get_product_details` with `8310926033` → `8310926303`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 21–22 | replays steps 13–14 (`get_order_details {"order_id":"#W9284598"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 80
**Root failure:** step 26 → 30 in the variant. The execution of the assistant ended prematurely because of system failure.

**Model's rationale:** The red herring makes the early order lookup look like a failed step: the user is unsure of the order ID, so a transposed-digit lookup returning "order not found" appears as a visible error before the agent retries and gets the correct order. The noise replays the read-only order lookup right after the user's email question, adding another order-detail exchange between the user's final confirmation request and the annotated step. Neither decoy changes the order state, so the trajectory continues unchanged.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W7209932` → `#W7290932`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 27–28 | replays steps 13–14 (`get_order_details {"order_id": "#W7209932"}`) after step 24 | ok |

**Suggested:** accept

## Trajectory 82
**Root failure:** step 20 → 24 in the variant. At step 20, the user agent asked the assistant to the return the tablets from both the orders, however, it was supposed to ask to return all the items from a single order, hence, did not follow the task instruction

**Model's rationale:** The annotated failure is the user's step 20, where they ask to return the tablets from both orders instead of all items from one order. The red herring is a mistyped order lookup before the order #W8171054 check: it fails with a plausible "order not found" error, then the same lookup succeeds, adding a visible error just before the user's confusing request. The noise replays the earlier read of order #W3069600 between the order checks and the assistant's summary, lengthening the trajectory with harmless read-only output. Neither decoy changes any state or alters what follows.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W8171054` → `#W8171045`, answered `Error: order not found`; original step 15 is the retry | ok |
| noise | 21–22 | replays steps 11–12 (`get_order_details {"order_id": "#W3069600"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 87
**Root failure:** step 37 → 41 in the variant. The assistant agent should have modified all the three pending order addresses but it only modified the first two pending order addresses and claimed that it completed all the updates.

**Model's rationale:** The first decoy inserts a failed lookup of the pending order #W6832752 with a transposed digit, answered by an error, just before the successful retrieval of that same order. This makes the third pending order look like a lookup problem the agent resolved, pulling attention toward the order-retrieval steps rather than the missing modification. The second decoy replays the read-only lookup of delivered order #W7739115 between the two modifications and the default-address update, adding output between the evidence and the failure without changing any state. Both give the evaluator plausible-looking trouble that is not the cause.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 23–24 | `get_order_details` with `#W6832752` → `#W6832725`, answered `Error: order not found`; original step 23 is the retry | ok |
| noise | 37–38 | replays steps 25–26 (`get_order_details {"order_id":"#W7739115"}`) after step 34 | writes in between on other entities: step 31 `modify_pending_order_address`, step 33 `modify_pending_order_address` |

**Suggested:** accept

## Trajectory 91
**Root failure:** step 34 → 40 in the variant. The user agent asked the assistant to also return the tablet from order #W3239882, however, this was not specified in the original task instruction.

**Model's rationale:** The first red herring makes the agent's lookup of order #W3239882 fail on a transposed digit just before the user's return request is discussed, so the order lookup appears to have gone wrong. The second is a failed product lookup for the e-reader's product ID, which puts a visible error right before the user's exchange discussion. The noise decoy re-reads order #W7553978 just before the user asks to recheck recent orders, adding an extra read-only exchange between the user's request and the assistant's listing. All three are read-only and harmless, and they make the trajectory look like it has multiple lookup problems, which could pull an evaluator away from the user's unsupported request for the tablet return at step 34.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W3239882` → `#W3239828`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 19–20 | `get_product_details` with `3801771308` → `3801771380`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 35–36 | replays steps 9–10 (`get_order_details {"order_id": "#W7553978"}`) after step 30 | ok |

**Suggested:** accept

## Trajectory 98
**Root failure:** step 21 → 25 in the variant. The assistant agent first modified the items in the pending orders before modifying the addresses which locked the orders and hence couldn't update the shipping addresses later. The correct sequence should have been vice-versa.

**Model's rationale:** The red herring makes the agent's lookup of the NYC order fail on a transposed digit right before the address lookup, so the user's address-update request seems to be the troubled part and draws attention to the address workflow. The noise replays the pending LA order's details (#W6750959, still pending and unchanged) just before the item modification, adding a reassuring status check that makes the modify call look correct and lengthens the span between the evidence and the failure.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 19–20 | `get_order_details` with `#W3407479` → `#W3407497`, answered `Error: order not found`; original step 19 is the retry | ok |
| noise | 23–24 | replays steps 9–10 (`get_order_details {"order_id": "#W6750959"}`) after step 20 | writes in between on other entities: step 15 `exchange_delivered_order_items` |

**Suggested:** accept

## Trajectory 99
**Root failure:** step 35 → 39 in the variant. The assistant while exchanging the delivered order items used the incorrect credit card. The task instruction and consequently the user mentions to use the other credit card on file, but it uses the same credit card. This could have been avoided if the assistant had confirmed the payment method with the user before proceeding with the exchange.

**Model's rationale:** The red herring adds a visible "product not found" error from a camera product lookup shortly before the failure, which looks like the camera exchange is going wrong when it is just a self-corrected lookup slip. The noise replays the read-only order lookup for #W4689314 right after the user's refund request, so the exchange-order details sit between the user's payment instruction and the failing exchange call, diluting attention on the payment_method_id choice at step 35.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 31–32 | `get_product_details` with `8940227892` → `8940227829`, answered `Error: product not found`; original step 31 is the retry | ok |
| noise | 37–38 | replays steps 11–12 (`get_order_details {"order_id": "#W4689314"}`) after step 34 | writes in between on other entities: step 29 `exchange_delivered_order_items` |

**Suggested:** accept

## Trajectory 104
**Root failure:** step 57 → 61 in the variant. The assistant mentioned to the user that the cancelled order #W1154986 did not have a tracking number. However, this is not true as in the tool output of get_order_details for order #W1154986, a tracking number is clearly present.

**Model's rationale:** The red herring makes the cancelled order #W1154986 look like a failed lookup early on, so the later tracking question seems to involve a suspect or unreliable record, which could make the evaluator doubt the successful tool output at step 16. The noise replay of the delivered order #W8660475 (unchanged, so the same result) adds an extra order-detail exchange between the evidence and the failure, lengthening the trajectory without changing any state.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W1154986` → `#W1154896`, answered `Error: order not found`; original step 15 is the retry | ok |
| noise | 41–42 | replays steps 13–14 (`get_order_details {"order_id": "#W8660475"}`) after step 38 | writes in between on other entities: step 27 `return_delivered_order_items`, step 35 `return_delivered_order_items` |

**Suggested:** accept

## Trajectory 105
**Root failure:** step 43 → 47 in the variant. The assistant tries to modify the address after the modifying the pending order items which is not supported currently per the domain policy.

**Model's rationale:** The red herring adds a visible "order not found" failure right before the pending-order lookup, a transposed-digit slip that the assistant corrects on retry. It makes the order ID look like an early source of trouble for the later pending-order work, which is a distraction from the real problem. The noise replays the read-only profile lookup (get_user_details) between the user's address request and the failing address call. It returns the same profile, so it adds output between the item modification and the address attempt without changing any state. Neither decoy changes the order state or the sequence that follows.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 33–34 | `get_order_details` with `#W4860251` → `#W4860521`, answered `Error: order not found`; original step 33 is the retry | ok |
| noise | 45–46 | replays steps 9–10 (`get_user_details {"user_id":"lucas_brown_6720"}`) after step 42 | writes in between on other entities: step 17 `return_delivered_order_items`, step 19 `return_delivered_order_items`, step 29 `return_delivered_order_items`, step 39 `modify_pending_order_items` |

**Suggested:** accept (checked: step 39 modify_pending_order_items charged credit_card_2112420; the replayed profile shows only that card's brand and last four (no balance) and its order list is unchanged, so the replay is current)

