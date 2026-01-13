
import re
import sys

def normalize(text):
    """Normalize whitespace: collapse multiple spaces/newlines to single space and strip."""
    if not text:
        return ""
    return ' '.join(text.split())

def build_index(file_path):
    print(f"Indexing {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None

    exact_index = {}
    relaxed_index = {}
    
    # Iterate over contexts
    # Pattern designed to be non-greedy but handle newlines (assignments are implied by DOTALL)
    context_pattern = re.compile(r'<context>(.*?)</context>', re.DOTALL)
    name_pattern = re.compile(r'<name>(.*?)</name>', re.DOTALL)
    message_pattern = re.compile(r'<message>(.*?)</message>', re.DOTALL)
    source_pattern = re.compile(r'<source>(.*?)</source>', re.DOTALL)
    translation_pattern = re.compile(r'<translation(.*?)>(.*?)</translation>', re.DOTALL)

    for cmatch in context_pattern.finditer(content):
        context_body = cmatch.group(1)
        nmatch = name_pattern.search(context_body)
        if not nmatch:
            continue
        context_name = nmatch.group(1).strip() # Names are usually short and safe to strip generally
        
        for mmatch in message_pattern.finditer(context_body):
            message_body = mmatch.group(1)
            
            smatch = source_pattern.search(message_body)
            if not smatch:
                continue
            
            source_raw = smatch.group(1)
            
            tmatch = translation_pattern.search(message_body)
            if not tmatch:
                continue
            
            translation_content = tmatch.group(2)
            
            # Store keys
            key_exact = (context_name, source_raw)
            key_relaxed = (context_name, normalize(source_raw))
            
            exact_index[key_exact] = translation_content
            relaxed_index[key_relaxed] = translation_content
            
    print(f"Index built. Exact keys: {len(exact_index)}, Relaxed keys: {len(relaxed_index)}")
    return exact_index, relaxed_index

def get_line_number(content, offset):
    return content.count('\n', 0, offset) + 1

def process_target(target_path, exact_index, relaxed_index):
    print(f"Processing {target_path}...")
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {target_path}: {e}")
        return

    replacements = [] # List of (start, end, new_text)
    
    stats_exact = 0
    stats_relaxed = 0
    stats_unmatched = 0
    
    context_pattern = re.compile(r'<context>(.*?)</context>', re.DOTALL)
    name_pattern = re.compile(r'<name>(.*?)</name>', re.DOTALL)
    message_pattern = re.compile(r'<message>(.*?)</message>', re.DOTALL)
    source_pattern = re.compile(r'<source>(.*?)</source>', re.DOTALL)
    translation_pattern = re.compile(r'<translation(.*?)>(.*?)</translation>', re.DOTALL)
    
    # We define patterns again to use identical logic
    
    for cmatch in context_pattern.finditer(content):
        c_start = cmatch.start(1)
        context_body = cmatch.group(1)
        
        nmatch = name_pattern.search(context_body)
        if not nmatch:
            continue # Should not happen in valid TS
        context_name = nmatch.group(1).strip()
        
        for mmatch in message_pattern.finditer(context_body):
            m_start_rel = mmatch.start(1)
            message_body = mmatch.group(1)
            
            smatch = source_pattern.search(message_body)
            if not smatch:
                continue
            
            source_raw = smatch.group(1)
            source_norm = normalize(source_raw)
            
            tmatch = translation_pattern.search(message_body)
            if not tmatch:
                continue # If no translation tag, skip
                
            # Identify location of translation content for replacement
            # tmatch.group(2) is the content.
            # absolute start = c_start + m_start_rel + tmatch.start(2)
            # absolute end = c_start + m_start_rel + tmatch.end(2)
            
            abs_start = c_start + m_start_rel + tmatch.start(2)
            abs_end = c_start + m_start_rel + tmatch.end(2)
            
            # Lookup
            new_content = None
            if (context_name, source_raw) in exact_index:
                # Exact match
                new_content = exact_index[(context_name, source_raw)]
                # Check if change matches current? (Optimisation: skip if identical)
                if new_content != tmatch.group(2):
                     replacements.append((abs_start, abs_end, new_content))
                stats_exact += 1
            elif (context_name, source_norm) in relaxed_index:
                # Relaxed match
                new_content = relaxed_index[(context_name, source_norm)]
                line_num = get_line_number(content, abs_start)
                print(f"Relaxed match at line {line_num}: Context='{context_name}'")
                replacements.append((abs_start, abs_end, new_content))
                stats_relaxed += 1
            else:
                stats_unmatched += 1
                
    # Apply replacements backwards
    replacements.sort(key=lambda x: x[0], reverse=True)
    
    new_content_list = list(content)
    # Using string slicing is easier but string is immutable.
    # Constructing parts.
    
    # Efficient application:
    cursor = len(content)
    final_parts = []
    
    for start, end, text in replacements:
        # Append part after valid replacement
        final_parts.append(content[end:cursor])
        final_parts.append(text)
        cursor = start
    final_parts.append(content[0:cursor])
    
    final_parts.reverse()
    result_content = "".join(final_parts)
    
    print(f"Stats: Exact Matches: {stats_exact}, Relaxed Matches: {stats_relaxed}, Unmatched: {stats_unmatched}")
    print(f"Writing updated content to {target_path}...")
    
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(result_content)
    print("Done.")

if __name__ == "__main__":
    update_file = r"qtcreator_zh_CN_translated_18.0.xml"
    target_file = r"qtcreator_zh_CN_lupdate.xml"
    
    exact, relaxed = build_index(update_file)
    if exact is not None:
        process_target(target_file, exact, relaxed)
