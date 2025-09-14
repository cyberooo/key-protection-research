## This folder contains the results of the keystore exploration and app extraction.

* "all_app_signature.txt" contains the signature of the APK files that we have collected.

* "keystore_results_decrypted_202408.json" contains the keystores that we managed to decrypt in our last collection during the longitudinal study, which took place in the mid of August 2024. 

* "all_results_gradle_and_keystore_search_202408.zip" contains all the Gradle and keystore files found in our longitudinal GitHub search in August 2024. Note that only finding a Gradle file in a repository without a keystore being uploaded, even if the password is hardcoded in plaintext, does not constitute a key leakage.

> Note that for ethical considerations, we cannot share all results of the keystore leakage because it will massively disclose the GitHub users who are involved in this key leakage. Although these repositories are no longer accessible, we still want to maximize our protection of the anonymity of different parties involved in the key leakage incident. Instead, we share the raw results of our last collection in August 2024 only. We also kindly ask anonymous reviewers not to share or abuse these results.
