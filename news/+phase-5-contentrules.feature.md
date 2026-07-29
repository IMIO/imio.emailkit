Add the *"Send styled email"* content-rule action: the edit form offers every
template SPEC §4 discovery knows about, through a new
`imio.emailkit.templates` vocabulary, plus two recipient sources (an explicit
list of addresses or user ids, and the triggering content's owner). The executor
delegates to the `Email` builder, so per-language sending, the registration's
subject and transaction-safe delivery come for free, and it never swallows an
error. The stock mail action is untouched. SPEC §8.3.
