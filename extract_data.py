with open("full_dump_main.sql", "r") as f_in, open("data_only.sql", "w") as f_out:
    f_out.write("SET session_replication_role = 'replica';\n")
    in_copy_block = False
    for line in f_in:
        if line.startswith("COPY public."):
            in_copy_block = True
            
        if in_copy_block:
            f_out.write(line)
            if line.strip() == "\.":
                in_copy_block = False
