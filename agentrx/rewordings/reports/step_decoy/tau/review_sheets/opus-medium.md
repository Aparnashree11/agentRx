# Review sheet: runs/decoy/tau/opus-medium

Model `claude-opus-5-5`, effort `medium`, domain `tau`.
Flags come from Tau-specific heuristics in this review script, not from the generator.
Fill `decision` (accept/reject), `reviewer` and `reason` in `reviews.json`; blanks are refused at release.
Suggestions: 27 accept, 1 reject (31: stale gift-card balance); 47 has no candidate (a red herring with no actual slip).


## Trajectory 2
**Root failure:** step 7 → 13 in the variant. At step 7, the agent did not correctly count the number of available t-shirts from the tool call result.

**Model's rationale:** The red herring puts a visible tool error, a product lookup with a transposed ID, just before the T-shirt details are fetched. An evaluator may blame that failed lookup instead of the count. Replaying the T-shirt product details adds a second copy of the variant list right before the agent's answer. Replaying the product-type listing makes the run before the failure longer. All three are read-only and the agent had already made them at those points, so their results would not change.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 7–8 | `get_product_details` with `9523456873` → `9523465873`, answered `Error: product not found`; original step 5 is the retry | ok |
| noise | 11–12 | replays steps 5–6 (`get_product_details {"product_id":"9523456873"}`) after step 6 | ok |
| noise | 5–6 | replays steps 3–4 (`list_all_product_types {}`) after step 4 | ok |

**Suggested:** accept

## Trajectory 3
**Root failure:** step 7 → 11 in the variant. At step 7, the agent did not correctly count the number of available t-shirts from the tool call result.

**Model's rationale:** The red herring adds a failed product lookup with two transposed digits in the product ID just before the real lookup. It is a visible error close to the failure, but it is harmless: the retry succeeds with the correct T-Shirt ID. The noise decoy repeats the same read-only product-details lookup right after step 6. Nothing changes the catalog in between, so it returns identical output. This puts a second copy of the variant list between the original evidence and the miscount at step 7, so an evaluator may focus on the retrieval steps rather than on how the agent read the result.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 5 is the retry | ok |
| noise | 9–10 | replays steps 5–6 (`get_product_details {"product_id":"9523456873"}`) after step 6 | ok |

**Suggested:** accept

## Trajectory 4
**Root failure:** step 15 → 23 in the variant. At step 15, the assistant agent incorrectly counted the number of available t-shirts.

**Model's rationale:** There are two failed lookups that are then retried. The first is a user ID with two swapped digits, answered by "user not found". The second is a T-Shirt product ID with two swapped digits, answered by "product not found". The second error appears just before the product listing, so an evaluator may suspect the product lookup step instead of the counting step. Two read-only replays add more output: a second profile lookup after the product types are listed, and a second, identical product-details response just before step 15. The repeated listing puts more text between the evidence and the wrong count, and may suggest a confusion from reading the list twice.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_user_details` with `yusuf_rossi_9620` → `yusuf_rossi_9602`, answered `Error: user not found`; original step 9 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 13 is the retry | ok |
| noise | 15–16 | replays steps 9–10 (`get_user_details {"user_id":"yusuf_rossi_9620"}`) after step 12 | ok |
| noise | 21–22 | replays steps 13–14 (`get_product_details {"product_id":"9523456873"}`) after step 14 | ok |

**Suggested:** accept

## Trajectory 12
**Root failure:** step 19 → 25 in the variant. At step 19, the assistant agent did not ask user for confirmation and payment method before initiating return.

**Model's rationale:** I chose three decoys, all before step 19. Two are failed lookups that the agent then retries: a profile lookup with a transposed user ID, and an order lookup with a transposed order ID. Both are read-only, so they fail without changing anything and create visible errors during the order checks. The third decoy re-reads order #W5490111 right after the think step and just before the return call. It looks like careful checking before the action, and it puts a large block of order data between the user's 'All of them' and the return call that writes to the database.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 7–8 | `get_user_details` with `mia_garcia_4516` → `mia_garcia_4561`, answered `Error: user not found`; original step 7 is the retry | ok |
| red_herring | 15–16 | `get_order_details` with `#W7387996` → `#W7389796`, answered `Error: order not found`; original step 13 is the retry | ok |
| noise | 23–24 | replays steps 11–12 (`get_order_details {"order_id": "#W5490111"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 20
**Root failure:** step 21 → 27 in the variant. At step 21, the assistant mistook two of the orders which were processed as delivered

**Model's rationale:** I added two failed order lookups, each caused by a transposed-digit order ID and each fixed right away. They sit on the same order fetches whose statuses the agent later misreads, so they put visible errors in the order-retrieval phase, close to the failure. I also replayed the user-profile read between the last order fetch and the summary. That puts extra output between the status evidence and step 21, which makes the status misreading harder to trace.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W4967593` → `#W4967539`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 19–20 | `get_order_details` with `#W5733668` → `#W5733686`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 23–24 | replays steps 9–10 (`get_user_details {"user_id":"ethan_garcia_1261"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 21
**Root failure:** step 28 → 34 in the variant. At step 28, the user agent insisted on exchange of an item in 'pending' status which is not valid according to domain policy, when assistant asked if it could instead modify (corresponds to the ground truth), the user agent said no.

**Model's rationale:** I added three decoys before the failure at step 28. Each one makes the assistant's side look shaky, but none of them changes any state.
1. Before step 15, the agent mistypes an order ID (#W5733686 instead of #W5733668) and gets an error. The real lookup at step 15 then reads as the successful retry.
2. After the think step at 20, the agent re-reads the details of the pending order #W9911714. This fits its stated plan to "double-check the fulfillment details" and gives the same result, because nothing changed in between.
3. Right before the user's step 28, the agent mistypes the shoe product ID (6938111401 instead of 6938111410) and gets an error. That puts a visible tool failure close to the failure step.
The two errors and the extra lookup may lead an evaluator to blame the assistant's handling of the order, not the user's invalid request. "Error: order not found" and "Error: product not found" are my guesses at the tool's wording, modelled on the logged "Error: user not found". No example in the data matches these requests exactly.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W5733668` → `#W5733686`, answered `Error: order not found`; original step 15 is the retry | ok |
| noise | 23–24 | replays steps 13–14 (`get_order_details {"order_id": "#W9911714"}`) after step 20 | ok |
| red_herring | 27–28 | `get_product_details` with `6938111410` → `6938111401`, answered `Error: product not found`; original step 23 is the retry | ok |

**Suggested:** accept

## Trajectory 28
**Root failure:** step 33 → 41 in the variant. At step 33,  the assistant mistakenly believes that it can cancel a subset of a pending order which is not allowed as per domain policy, as a result the entire order got cancelled instead of just the garden hose.

**Model's rationale:** I added four decoys: two failed lookups that are retried and two harmless re-reads. First, the login lookup is tried once with the zip code's digits swapped (32268), returns "user not found", and then succeeds. Second, the lookup of the pending order is tried with a mistyped order ID (#W2575353), returns "order not found", and then succeeds. Both are visible errors that change no data and are corrected right away. For the noise, the assistant re-reads the user profile after the hose-cancel request at step 30. It also re-reads pending order #W2575533 right after the user confirms at step 32, which looks like the required status check before cancelling. That second re-read shows all five items in the order just before the cancel call, which may make the cancel look properly checked and draw attention to the earlier lookups instead.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_name_zip` with `32286` → `32268`, answered `Error: user not found`; original step 5 is the retry | ok |
| red_herring | 19–20 | `get_order_details` with `#W2575533` → `#W2575353`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 35–36 | replays steps 7–8 (`get_user_details {"user_id":"isabella_johansson_2152"}`) after step 30 | writes in between on other entities: step 23 `return_delivered_order_items`, step 25 `return_delivered_order_items`, step 27 `return_delivered_order_items` |
| noise | 39–40 | replays steps 17–18 (`get_order_details {"order_id":"#W2575533"}`) after step 32 | writes in between on other entities: step 23 `return_delivered_order_items`, step 25 `return_delivered_order_items`, step 27 `return_delivered_order_items` |

**Suggested:** accept (checked: returns refund to PayPal; the profile has no balance field, so the replay is current)

## Trajectory 31
**Root failure:** step 31 → 39 in the variant. At step 31, the assistant mistakenly believes that it can cancel a subset of a pending order which is not allowed as per domain policy, as a result the entire order got cancelled instead of just the hiking boots.

**Model's rationale:** A failed order lookup with a transposed ID just before the boot/kettle order is fetched puts a visible error near the failure. A similar failed lookup during the charger cancellation adds another error earlier on. Re-reading the profile after the user names the boot, kettle and sneaker, and re-checking order #W5481803 right before the cancel call, add read-only output between the evidence (the order holds both kettle and boots) and the wrong full-order cancellation. All inserted calls are reads, happen after authentication, and return the same data at their new positions.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| noise | 29–30 | replays steps 7–8 (`get_user_details {"user_id":"olivia_lopez_3865"}`) after step 26 | writes in between on other entities: step 23 `cancel_pending_order` |
| red_herring | 31–32 | `get_order_details` with `#W5481803` → `#W5481830`, answered `Error: order not found`; original step 27 is the retry | ok |
| noise | 37–38 | replays steps 27–28 (`get_order_details {"order_id":"#W5481803"}`) after step 30 | ok |
| red_herring | 19–20 | `get_order_details` with `#W9373487` → `#W9373478`, answered `Error: order not found`; original step 19 is the retry | ok |

**Suggested:** reject (stale: step 23 cancel_pending_order refunded 109.27 to gift_card_7711863, but the replayed profile still shows balance 44)

## Trajectory 32
**Root failure:** step 11 → 17 in the variant. At step 11, the assistant mistakenly provided tracking number of wrong order which did not even contain the tablet.

**Model's rationale:** I added three decoys, all before step 11. The first is a failed authentication: the zip code is typed as 76117 instead of 76171, the lookup returns "user not found", and the retry succeeds. The second is a harmless second read of the user profile. The third is an order lookup with transposed digits (#W7449580), which returns "order not found" just before the real lookup of #W7449508. Together they put visible errors and repeated output right before the tracking-number answer. An evaluator could blame the lookup slips or wonder why the agent picked that order. None of them changes any state, and each slip is fixed right away.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_name_zip` with `76171` → `76117`, answered `Error: user not found`; original step 5 is the retry | ok |
| noise | 11–12 | replays steps 7–8 (`get_user_details {"user_id":"olivia_lopez_3865"}`) after step 8 | ok |
| red_herring | 13–14 | `get_order_details` with `#W7449508` → `#W7449580`, answered `Error: order not found`; original step 9 is the retry | ok |

**Suggested:** accept

## Trajectory 34
**Root failure:** step 17 → 25 in the variant. At step 17, the assistant uses modify order to cancel a subset of orders, however modify orders also need to have a replacement, which it did not provide resulting in an illegal tool call

**Model's rationale:** I added two failed lookups early on. One mistypes the user ID and the other mistypes the order ID. Each is fixed right away, so it shows a visible error without changing what happens later. I also added two read-only replays just before the failure. The first re-reads the user profile, which fits as a check of the payment method before the refund question. The second re-fetches the order, which fits as a status check before the modify call. These replays put tool output between the user's confirmation and the faulty modify call, so the failure is harder to pick out.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_user_details` with `noah_patel_6952` → `noah_patel_6925`, answered `Error: user not found`; original step 9 is the retry | ok |
| red_herring | 13–14 | `get_order_details` with `#W1845024` → `#W1845042`, answered `Error: order not found`; original step 11 is the retry | ok |
| noise | 19–20 | replays steps 9–10 (`get_user_details {"user_id":"noah_patel_6952"}`) after step 14 | ok |
| noise | 23–24 | replays steps 11–12 (`get_order_details {"order_id":"#W1845024"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 38
**Root failure:** step 37 → 43 in the variant. At step 37, for the umbrella, it picks an item that is cheapest but is not available. the assistant is not able to correctly compare the item prices to figure which is the cheapest one.

**Model's rationale:** I added three decoys, all of them read-only lookups that change no state. The first two are failed lookups that get retried. The agent mistypes the Patio Umbrella product ID once, swapping two digits, and gets an error before the original call succeeds. It does the same with the T-Shirt product ID. These visible errors sit inside the price-comparison phase, so an evaluator might blame a failed lookup instead of the wrong pick. The umbrella error is the strongest lure, since that is the product where the real mistake happens. The third decoy repeats the order-details lookup after the backpack details come back. That adds a long block of output between the product listings and the price calculation at step 37. The user, order and products stay the same, and every call is allowed after authentication.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 27–28 | `get_product_details` with `9743693396` → `9743639396`, answered `Error: product not found`; original step 27 is the retry | ok |
| red_herring | 33–34 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 31 is the retry | ok |
| noise | 39–40 | replays steps 13–14 (`get_order_details {"order_id":"#W9348897"}`) after step 34 | ok |

**Suggested:** accept

## Trajectory 39
**Root failure:** step 17 → 23 in the variant. At step 17, the assistant agent believes that it cannot find the latest address from the current orders using get_order_details and hence is unable to modify the existing user address in an order to the latest one.

**Model's rationale:** I added three decoys, all before step 17 and all read-only. Two are failed lookups that get retried. The first is a name and zip lookup with the zip digits swapped (32196), which gives the same "user not found" error the email lookup already returned. Together the two errors look like a tangle of authentication failures. The second is a profile lookup with the last two digits of the user ID swapped (fatima_taylor_3425). It also fails and then works on the retry. Both read as sloppy handling of IDs early on. The third decoy is a replay of the profile read, placed right after the user asks the agent to take the address from her order details. The agent appears to do something in response, but it reads the profile again instead of calling get_order_details on #W5285031. That puts extra output between the request and the agent's wrong refusal. Nothing after the decoys changes, because each retry succeeds and the replayed profile read returns the same result as before.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `find_user_id_by_name_zip` with `32169` → `32196`, answered `Error: user not found`; original step 9 is the retry | ok |
| red_herring | 13–14 | `get_user_details` with `fatima_taylor_3452` → `fatima_taylor_3425`, answered `Error: user not found`; original step 11 is the retry | ok |
| noise | 21–22 | replays steps 11–12 (`get_user_details {"user_id":"fatima_taylor_3452"}`) after step 16 | ok |

**Suggested:** accept

## Trajectory 41
**Root failure:** step 17 → 25 in the variant. At step 17, the assistant agent modified the items in the pending order which locked it and hence cannot update the shipping address later, hence the order of tool calling should have been vice-versa.

**Model's rationale:** I added two failed lookups that the agent then retries: a mistyped order ID and a mistyped product ID. Each shows a visible error on the jigsaw-order path shortly before the failure. I also added two harmless repeat reads: the user profile again, and order #W4082615 again just before the summary. These put extra output between the address evidence and the action in step 17. All the inserted calls only read data and happen after authentication, and nothing changes after them.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W4082615` → `#W4082651`, answered `Error: order not found`; original step 11 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `1808611083` → `1808611038`, answered `Error: product not found`; original step 13 is the retry | ok |
| noise | 15–16 | replays steps 7–8 (`get_user_details {"user_id":"mei_patel_7272"}`) after step 12 | ok |
| noise | 21–22 | replays steps 11–12 (`get_order_details {"order_id":"#W4082615"}`) after step 14 | ok |

**Suggested:** accept

## Trajectory 47
No release candidate: A red herring needs find, a different replace_with, and a response

## Trajectory 55
**Root failure:** step 32 → 40 in the variant. The user asked the assistant to return the air purifier, smart watch, and coffee maker while it should have also asked it to return the water bottle from the order according to the task instruction.

**Model's rationale:** I added two failed lookups, each caused by a transposed ID: one for the user profile and one for order #W4597054, the order where the failure happens. Each is retried successfully right away, so the trajectory shows visible errors on the same entity without anything changing afterwards. I also added two harmless re-reads. One re-checks the hiking boots order after the full order scan. The other re-reads #W4597054 just after the cancellations, so there is extra read-only output right before the user's incomplete return request. These additions make the assistant's handling of that order look like the trouble spot, when the real cause is the user's request.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 9–10 | `get_user_details` with `amelia_silva_7726` → `amelia_silva_7762`, answered `Error: user not found`; original step 9 is the retry | ok |
| red_herring | 19–20 | `get_order_details` with `#W4597054` → `#W4597045`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 29–30 | replays steps 21–22 (`get_order_details {"order_id": "#W7773202"}`) after step 24 | ok |
| noise | 37–38 | replays steps 17–18 (`get_order_details {"order_id": "#W4597054"}`) after step 30 | writes in between on other entities: step 27 `cancel_pending_order`, step 29 `cancel_pending_order` |

**Suggested:** accept

## Trajectory 59
**Root failure:** step 14 → 22 in the variant. The user agent incorrectly assumed that one order was older than the other even when the assistant specifically mentioned that it did not have the chronological information regarding the orders' placement date. It led to the incorrect order being cancelled compared to ground truth actions.

**Model's rationale:** I added three failed lookups that the agent retries and fixes: a misspelled first name during login and a transposed digit in each order ID. Each one returns a visible tool error before the agent explains the order statuses, so an evaluator may suspect the lookups went wrong. I also replayed the read of order #W2702727 just before the agent's explanation. That puts more order data between the evidence and the user's decision, and it may tempt an evaluator to look for a placement date in the order records or to blame the assistant's explanation in step 11. None of these changes any data, and the later steps still read correctly.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_name_zip` with `Yusuf` → `Yusef`, answered `Error: user not found`; original step 5 is the retry | ok |
| red_herring | 9–10 | `get_order_details` with `#W2702727` → `#W2702772`, answered `Error: order not found`; original step 7 is the retry | ok |
| red_herring | 13–14 | `get_order_details` with `#W8268610` → `#W8268601`, answered `Error: order not found`; original step 9 is the retry | ok |
| noise | 17–18 | replays steps 7–8 (`get_order_details {"order_id": "#W2702727"}`) after step 10 | ok |

**Suggested:** accept

## Trajectory 63
**Root failure:** step 32 → 40 in the variant. In step 32, the user agent asked the assistant to add an item to a pending order instead of replacing it with the cheaper item. This is because of unclear original task instruction.

**Model's rationale:** I added two failed lookups that the agent then retries successfully, plus two read-only replays. The first failed lookup is the authentication call with the zip code mistyped as 77040, which returns "user not found". The second is the product lookup with two digits of the product ID swapped, which returns "product not found". Both are visible tool errors that an evaluator could mistake for the source of the trouble. The replays are also read-only. One re-fetches the speaker product variants after the user asks about speakers under $300. The other re-reads the pending order #W5061109 right before the agent proposes the swap. Both put more tool output between the price evidence and step 32, which pulls attention toward the agent's handling of the order and away from the user's wording.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 7–8 | `find_user_id_by_name_zip` with `77004` → `77040`, answered `Error: user not found`; original step 7 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `4768869376` → `4768869367`, answered `Error: product not found`; original step 15 is the retry | ok |
| noise | 29–30 | replays steps 15–16 (`get_product_details {"product_id":"4768869376"}`) after step 24 | ok |
| noise | 37–38 | replays steps 13–14 (`get_order_details {"order_id":"#W5061109"}`) after step 30 | ok |

**Suggested:** accept

## Trajectory 71
**Root failure:** step 24 → 32 in the variant. At step 24, the task instruction did not specify the type of black lamp and since there are multiple black lamps available, it wont be possible to match the ground truth actions.

**Model's rationale:** Two retried lookups add visible tool errors: a misspelled last name during authentication, and a transposed desk lamp product ID right before the lamp options are fetched. Two read-only replays (re-reading the profile and the order) lengthen the stretch between the lamp options and the user's choice. Together they draw attention to agent-side errors and redundant lookups instead of the user's arbitrary lamp choice at step 24. Each error is corrected immediately and the replays return the same data, so nothing that follows changes.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_name_zip` with `Khan` → `Kahn`, answered `Error: user not found`; original step 5 is the retry | ok |
| noise | 21–22 | replays steps 11–12 (`get_user_details {"user_id":"ivan_khan_7475"}`) after step 18 | ok |
| red_herring | 23–24 | `get_product_details` with `6817146515` → `6817146551`, answered `Error: product not found`; original step 19 is the retry | ok |
| noise | 27–28 | replays steps 15–16 (`get_order_details {"order_id": "#W5270061"}`) after step 20 | ok |

**Suggested:** accept

## Trajectory 72
**Root failure:** step 21 → 29 in the variant. At step 21, the assistant modifies order items before modifying address which locks in the order and hence is unable to modify the shipping address later.

**Model's rationale:** I added two failed lookups that are then retried, plus two repeated reads. First, an order lookup with a transposed ID fails and is retried. Second, a desk lamp product lookup with a transposed ID fails just a few steps before the faulty modify call. Both show visible errors that an evaluator may wrongly blame. The repeated reads add the user profile again after the order is found, and the order details again right before the think step. This puts more read-only output between the evidence and step 21: the order is pending and still ships to the DC address, and the user asked for both the item change and the address change. Every inserted request is a read that changes no state. Each one comes after authentication and refers to the same user and order.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 11–12 | `get_order_details` with `#W5270061` → `#W5270016`, answered `Error: order not found`; original step 11 is the retry | ok |
| red_herring | 21–22 | `get_product_details` with `6817146515` → `6817146551`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 15–16 | replays steps 7–8 (`get_user_details {"user_id":"ivan_khan_7475"}`) after step 12 | ok |
| noise | 25–26 | replays steps 11–12 (`get_order_details {"order_id": "#W5270061"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 74
**Root failure:** step 21 → 31 in the variant. At step 21, the agent called exchange order items tool on an order which is still in pending status which is invalid.

**Model's rationale:** I added three lookups that fail once and are then retried. Each one hits a mistyped value: the zip code during sign-in, the order ID, and the product ID. These errors show up early, before the real failure, and look like the agent mishandling IDs. I also added two read-only repeats. One re-reads the user's profile after the order lookup. The other re-reads the order details just before the exchange call. They make the trajectory longer and put more tool output between the agent seeing the order status and the bad exchange call. None of these steps changes any data, and every later step stays valid.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W5166363` → `#W5166336`, answered `Error: order not found`; original step 11 is the retry | ok |
| red_herring | 19–20 | `get_product_details` with `4760268021` → `4760268012`, answered `Error: product not found`; original step 13 is the retry | ok |
| red_herring | 5–6 | `find_user_id_by_name_zip` with `85033` → `85303`, answered `Error: user not found`; original step 5 is the retry | ok |
| noise | 17–18 | replays steps 9–10 (`get_user_details {"user_id":"lei_li_6575"}`) after step 12 | ok |
| noise | 29–30 | replays steps 11–12 (`get_order_details {"order_id": "#W5166363"}`) after step 20 | ok |

**Suggested:** accept

## Trajectory 79
**Root failure:** step 20 → 26 in the variant. The task instruction did not specify the color of the 1000ml bottle to be exchanged whether it was red or black. Because of this ambiguity, the user agent picked the black bottle whereas the ground truth as the red variant which did not correspond with the ground truth actions. The red variant instead matched the ground truth.

**Model's rationale:** I chose three decoys, all placed before the failure at step 20. The first is a failed order lookup caused by a transposed digit (#W9284958), which the agent then retries successfully. The second is a failed product-details lookup with transposed digits (8310962033), retried right before the variant list arrives. Both put visible tool errors near the point where the options are presented. The third replays the read-only lookup of order #W8661412 after the product variants come back, so extra output sits between the variant list and the user's choice. All three are read-only, come after authentication and leave nothing different afterwards, so every later step still reads the same.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W9284598` → `#W9284958`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 19–20 | `get_product_details` with `8310926033` → `8310962033`, answered `Error: product not found`; original step 17 is the retry | ok |
| noise | 23–24 | replays steps 9–10 (`get_order_details {"order_id": "#W8661412"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 80
**Root failure:** step 26 → 34 in the variant. The execution of the assistant ended prematurely because of system failure.

**Model's rationale:** I added two failed lookups that the agent fixes itself. One is an order ID with swapped digits, which returns "order not found". The other is a product ID with swapped digits, which returns "product not found". Both put visible tool errors earlier in the trajectory, and an evaluator might blame them. I also added two harmless repeat reads. The agent re-reads the user's profile when the user questions the gift card balance. It re-reads the product details just before the final confirmation. This puts more tool output close to the end, so a reader could suspect the agent of a data or calculation mistake rather than the system cutting the run short. None of the inserts changes any state, and the original call that follows each failed lookup works as before.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W7209932` → `#W7290932`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 17–18 | `get_product_details` with `9523456873` → `9523456837`, answered `Error: product not found`; original step 15 is the retry | ok |
| noise | 25–26 | replays steps 11–12 (`get_user_details {"user_id":"amelia_gonzalez_4098"}`) after step 20 | ok |
| noise | 31–32 | replays steps 15–16 (`get_product_details {"product_id":"9523456873"}`) after step 24 | ok |

**Suggested:** accept

## Trajectory 82
**Root failure:** step 20 → 28 in the variant. At step 20, the user agent asked the assistant to the return the tablets from both the orders, however, it was supposed to ask to return all the items from a single order, hence, did not follow the task instruction

**Model's rationale:** I added two failed lookups that are then retried, and two harmless re-reads. First, the agent mistypes the zip as 46218, gets "Error: user not found", and retries correctly. Second, it mistypes the ID of the second tablet order and gets "Error: order not found" right before it reads the tablet and payment details, close to where things go wrong. The noise steps re-read the user profile, including the gift card balance and the credit card, and re-read order #W3069600 just before the agent sums up the options at step 19. This puts extra payment and order data between the evidence and the user's request at step 20. These visible errors and the extra data around payment methods could make an evaluator suspect a lookup or payment-reasoning mistake by the agent.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_name_zip` with `46281` → `46218`, answered `Error: user not found`; original step 5 is the retry | ok |
| red_herring | 21–22 | `get_order_details` with `#W9571698` → `#W9517698`, answered `Error: order not found`; original step 17 is the retry | ok |
| noise | 15–16 | replays steps 7–8 (`get_user_details {"user_id":"chen_silva_7485"}`) after step 12 | ok |
| noise | 25–26 | replays steps 11–12 (`get_order_details {"order_id": "#W3069600"}`) after step 18 | ok |

**Suggested:** accept

## Trajectory 87
**Root failure:** step 37 → 45 in the variant. The assistant agent should have modified all the three pending order addresses but it only modified the first two pending order addresses and claimed that it completed all the updates.

**Model's rationale:** I added two failed order lookups caused by typed order IDs. One sits right where the third pending order (#W6832752) was found, and the other sits where the DC order was found. Each is followed by the original lookup succeeding as a retry. The visible errors are meant to look like the place where order information went missing. Then I replayed two read-only lookups. One re-reads order #W2166301 after the DC order is found. The other re-reads the profile after the user confirms. Both add pending-order and address output between the evidence and the modifications. Every replayed read happens after authentication and before any address change, so its result would be the same.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 23–24 | `get_order_details` with `#W6832752` → `#W6832725`, answered `Error: order not found`; original step 23 is the retry | ok |
| red_herring | 29–30 | `get_order_details` with `#W1994898` → `#W1994889`, answered `Error: order not found`; original step 27 is the retry | ok |
| noise | 33–34 | replays steps 11–12 (`get_order_details {"order_id": "#W2166301"}`) after step 28 | ok |
| noise | 37–38 | replays steps 9–10 (`get_user_details {"user_id":"yusuf_hernandez_6785"}`) after step 30 | ok |

**Suggested:** accept

## Trajectory 91
**Root failure:** step 34 → 40 in the variant. The user agent asked the assistant to also return the tablet from order #W3239882, however, this was not specified in the original task instruction.

**Model's rationale:** I added three decoys, and all of them are read-only lookups that fail or repeat without causing harm. The first is a slipped order ID in the lookup of the second order: two digits are swapped, so the call returns "order not found". The agent then retries with the correct ID. The second is a mistyped product ID in the smart watch availability check, which returns a "product not found" error before the correct lookup. Neither error message appears in the dataset's examples. I modeled them on the "Error: user not found" format. These visible errors on the assistant side could look like the place where the return/exchange plan started to go wrong. The third decoy is a re-read of the user profile placed just before the agent's list of items not yet covered. It adds tool output between the evidence and the user's off-script tablet request. None of these changes the information that comes after it.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 13–14 | `get_order_details` with `#W3239882` → `#W3238982`, answered `Error: order not found`; original step 13 is the retry | ok |
| red_herring | 27–28 | `get_product_details` with `6945232052` → `6945232025`, answered `Error: product not found`; original step 25 is the retry | ok |
| noise | 37–38 | replays steps 7–8 (`get_user_details {"user_id":"mei_ahmed_4909"}`) after step 32 | ok |

**Suggested:** accept

## Trajectory 98
**Root failure:** step 21 → 31 in the variant. The assistant agent first modified the items in the pending orders before modifying the addresses which locked the orders and hence couldn't update the shipping addresses later. The correct sequence should have been vice-versa.

**Model's rationale:** I added three failed lookups that are each retried right away. One is a mistyped NYC order ID just before step 19, a few steps before the failure. One is a transposed user ID before step 7, and one is a transposed product ID before step 11. Each gives a visible error that the agent then fixes. I also added two harmless re-reads. The LA order details are read again right after the NYC order is fetched, so pending-order output sits right before the item modification. The user profile is read again after the user's combined request at step 18. Together these put error messages and extra output close to step 21. None of them changes any state.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 25–26 | `get_order_details` with `#W3407479` → `#W3407497`, answered `Error: order not found`; original step 19 is the retry | ok |
| red_herring | 7–8 | `get_user_details` with `yusuf_li_7255` → `yusuf_li_7525`, answered `Error: user not found`; original step 7 is the retry | ok |
| red_herring | 13–14 | `get_product_details` with `4768869376` → `4768869367`, answered `Error: product not found`; original step 11 is the retry | ok |
| noise | 29–30 | replays steps 9–10 (`get_order_details {"order_id": "#W6750959"}`) after step 20 | writes in between on other entities: step 15 `exchange_delivered_order_items` |
| noise | 23–24 | replays steps 7–8 (`get_user_details {"user_id":"yusuf_li_7255"}`) after step 18 | writes in between on other entities: step 15 `exchange_delivered_order_items` |

**Suggested:** accept (checked: the only write in between (step 15 exchange) failed, so nothing changed)

## Trajectory 99
**Root failure:** step 35 → 41 in the variant. The assistant while exchanging the delivered order items used the incorrect credit card. The task instruction and consequently the user mentions to use the other credit card on file, but it uses the same credit card. This could have been avoided if the assistant had confirmed the payment method with the user before proceeding with the exchange.

**Model's rationale:** I added three decoys, all before the failure at step 35. First, a failed lookup of the camera product with transposed digits (8940227829) that returns a visible error. The agent then retries it successfully. This puts an error just before the faulty exchange. Second, a repeat read of camera order #W4689314 after the product details. That puts the order's payment history, which shows credit_card_8105988, close to the failing call. Third, a repeat read of the user profile right after the user asks for "the other card." This lists both cards just before the payment choice at step 35, so the profile read or the earlier error could look like where things went wrong. All three only read data, come after authentication, and return the same results because nothing in between changes them.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 31–32 | `get_product_details` with `8940227892` → `8940227829`, answered `Error: product not found`; original step 31 is the retry | ok |
| noise | 35–36 | replays steps 11–12 (`get_order_details {"order_id": "#W4689314"}`) after step 32 | writes in between on other entities: step 29 `exchange_delivered_order_items` |
| noise | 39–40 | replays steps 9–10 (`get_user_details {"user_id":"sofia_li_9219"}`) after step 34 | writes in between on other entities: step 29 `exchange_delivered_order_items` |

**Suggested:** accept (checked: step 29 exchange charged a credit card; the profile has no balance field, so the replay is current)

## Trajectory 104
**Root failure:** step 57 → 65 in the variant. The assistant mentioned to the user that the cancelled order #W1154986 did not have a tracking number. However, this is not true as in the tool output of get_order_details for order #W1154986, a tracking number is clearly present.

**Model's rationale:** I added two red herrings and two noise decoys. The first red herring is a failed lookup with a transposed digit in the cancelled order's ID (#W1154968), placed just before the real lookup at step 15. An evaluator might link this visible error to the later tracking-number answer. The second red herring is a failed product lookup with a transposed product ID, placed just before step 47. It puts another error near the end of the conversation. The first noise decoy re-reads the user profile before the address request. The second noise decoy re-reads order #W1154986 right after the user asks for the tracking number, which adds more tool output just before the wrong answer. Neither re-read changes any state, and both return the same result as the original call.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 15–16 | `get_order_details` with `#W1154986` → `#W1154968`, answered `Error: order not found`; original step 15 is the retry | ok |
| red_herring | 51–52 | `get_product_details` with `5426915165` → `5426915156`, answered `Error: product not found`; original step 47 is the retry | ok |
| noise | 41–42 | replays steps 7–8 (`get_user_details {"user_id":"lucas_brown_6720"}`) after step 38 | writes in between on other entities: step 27 `return_delivered_order_items`, step 35 `return_delivered_order_items` |
| noise | 63–64 | replays steps 15–16 (`get_order_details {"order_id":"#W1154986"}`) after step 56 | writes in between on other entities: step 27 `return_delivered_order_items`, step 35 `return_delivered_order_items`, step 43 `modify_pending_order_address`, step 53 `modify_pending_order_items` |

**Suggested:** accept (checked: returns on a credit card; the profile has no balance field, so the replay is current)

## Trajectory 105
**Root failure:** step 43 → 53 in the variant. The assistant tries to modify the address after the modifying the pending order items which is not supported currently per the domain policy.

**Model's rationale:** I added three failed lookups that the agent then retries successfully: a mistyped email during authentication, a transposed order ID when looking up the pending order, and a transposed product ID when checking the luggage options. Each shows a visible error, two of them near the pending-order modification, and none of them changes anything that follows. I also added two read-only repeats. The first re-reads the luggage product details just before the item change. The second re-reads the user profile just before the address change, which is a natural way to get the default Chicago address. That repeat sits between the confirmed item change and the failing address call, so the important order status is further from the failure. The repeats return the same data because neither the product availability nor the profile changed at those points.

| Kind | Variant steps | Decoy | Check |
|---|---|---|---|
| red_herring | 5–6 | `find_user_id_by_email` with `lucas.brown9344@example.com` → `lucas.brown9434@example.com`, answered `Error: user not found`; original step 5 is the retry | ok |
| red_herring | 35–36 | `get_order_details` with `#W4860251` → `#W4860215`, answered `Error: order not found`; original step 33 is the retry | ok |
| red_herring | 39–40 | `get_product_details` with `5426915165` → `5426915156`, answered `Error: product not found`; original step 35 is the retry | ok |
| noise | 45–46 | replays steps 35–36 (`get_product_details {"product_id":"5426915165"}`) after step 38 | ok |
| noise | 51–52 | replays steps 9–10 (`get_user_details {"user_id":"lucas_brown_6720"}`) after step 42 | writes in between on other entities: step 17 `return_delivered_order_items`, step 19 `return_delivered_order_items`, step 29 `return_delivered_order_items`, step 39 `modify_pending_order_items` |

**Suggested:** accept (checked: returns and an item change on a credit card; the profile has no balance field, so the replay is current)

