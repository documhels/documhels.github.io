def merge_sort(arr, key, reverse=False):
    # Convert tuples to lists (make them mutable)
    arr = [list(item) for item in arr]
    
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid], key, reverse)
    right = merge_sort(arr[mid:], key, reverse)
    
    return merge(left, right, key, reverse)

def merge(left, right, key, reverse=False):
    sorted_arr = []
    while left and right:
        if reverse:
            if left[0][key] > right[0][key]:  
                sorted_arr.append(left.pop(0))
            else:
                sorted_arr.append(right.pop(0))
        else:
            if left[0][key] < right[0][key]:  
                sorted_arr.append(left.pop(0))
            else:
                sorted_arr.append(right.pop(0))
    
    sorted_arr.extend(left)
    sorted_arr.extend(right)
    return sorted_arr