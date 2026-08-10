* 1. Parse the date using DMY format
gen a = date(clin2, "DMY")

* 2. Extract year and week
gen b = year(a)
gen c = week(a)

* 3. Flag Positive O1 cases 
gen d = strpos(v_chol, char(79)+char(49))
gen e = sign(d)

* 4. Collapse into weekly summary
collapse (count) f=v_chol (sum) g=e, by(b c)

* 5. Drop empty rows and sort the timeline
drop if b == .
sort b c
list b c f g